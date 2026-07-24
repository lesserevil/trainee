import AVFoundation
import AudioToolbox
import CoreAudio
import Darwin
import Foundation

private let streamMagic = Data("TRNEAUD1".utf8)
private let outputSampleRate = 16_000.0
private let maximumPendingBytes = 4 * 1024 * 1024

private struct CaptureError: LocalizedError {
  let message: String

  var errorDescription: String? {
    message
  }
}

private func checkStatus(_ status: OSStatus, _ operation: String) throws {
  guard status == noErr else {
    throw CaptureError(message: "\(operation) failed with Core Audio status \(status)")
  }
}

private func readDefaultOutputDevice() throws -> AudioObjectID {
  var address = AudioObjectPropertyAddress(
    mSelector: kAudioHardwarePropertyDefaultOutputDevice,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
  )
  var deviceID = AudioObjectID(kAudioObjectUnknown)
  var dataSize = UInt32(MemoryLayout<AudioObjectID>.size)
  let status = AudioObjectGetPropertyData(
    AudioObjectID(kAudioObjectSystemObject),
    &address,
    0,
    nil,
    &dataSize,
    &deviceID
  )
  try checkStatus(status, "Reading the default output device")
  guard deviceID != kAudioObjectUnknown else {
    throw CaptureError(message: "macOS has no default output audio device")
  }
  return deviceID
}

private func readDeviceUID(_ deviceID: AudioObjectID) throws -> String {
  var address = AudioObjectPropertyAddress(
    mSelector: kAudioDevicePropertyDeviceUID,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
  )
  var uid: CFString = "" as CFString
  var dataSize = UInt32(MemoryLayout<CFString>.size)
  let status = withUnsafeMutablePointer(to: &uid) { pointer in
    AudioObjectGetPropertyData(
      deviceID,
      &address,
      0,
      nil,
      &dataSize,
      pointer
    )
  }
  try checkStatus(status, "Reading the default output device identifier")
  return uid as String
}

private func readTapFormat(_ tapID: AudioObjectID) throws -> AudioStreamBasicDescription {
  var address = AudioObjectPropertyAddress(
    mSelector: kAudioTapPropertyFormat,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
  )
  var format = AudioStreamBasicDescription()
  var dataSize = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
  let status = AudioObjectGetPropertyData(
    tapID,
    &address,
    0,
    nil,
    &dataSize,
    &format
  )
  try checkStatus(status, "Reading the process tap format")
  return format
}

private final class PCMWriter: @unchecked Sendable {
  private let queue = DispatchQueue(label: "com.lesserevil.trainee.audio-writer")
  private let lock = NSLock()
  private let onOutputClosed: @Sendable () -> Void
  private var pendingBytes = 0
  private var isReady = false
  private var isClosed = false
  private var didNotifyClosure = false

  init(onOutputClosed: @escaping @Sendable () -> Void) {
    self.onOutputClosed = onOutputClosed
  }

  func markReady() throws {
    lock.lock()
    defer { lock.unlock() }

    guard !isClosed else {
      throw CaptureError(message: "The audio stream output was closed before capture started")
    }
    guard Self.writeAll(streamMagic) else {
      isClosed = true
      throw CaptureError(message: "Could not write the audio stream header")
    }
    isReady = true
  }

  func enqueue(_ data: Data) {
    lock.lock()
    guard isReady,
      !isClosed,
      pendingBytes + data.count <= maximumPendingBytes
    else {
      lock.unlock()
      return
    }
    pendingBytes += data.count
    lock.unlock()

    queue.async { [self] in
      let succeeded = Self.writeAll(data)

      lock.lock()
      pendingBytes -= data.count
      if !succeeded {
        isClosed = true
      }
      let shouldNotify = !succeeded && !didNotifyClosure
      if shouldNotify {
        didNotifyClosure = true
      }
      lock.unlock()

      if shouldNotify {
        onOutputClosed()
      }
    }
  }

  func close() {
    lock.lock()
    isClosed = true
    lock.unlock()
    queue.sync {}
  }

  private static func writeAll(_ data: Data) -> Bool {
    data.withUnsafeBytes { rawBuffer in
      guard let baseAddress = rawBuffer.baseAddress else {
        return true
      }

      var offset = 0
      while offset < rawBuffer.count {
        let result = Darwin.write(
          STDOUT_FILENO,
          baseAddress.advanced(by: offset),
          rawBuffer.count - offset
        )
        if result > 0 {
          offset += result
        } else if result == -1 && errno == EINTR {
          continue
        } else {
          return false
        }
      }
      return true
    }
  }
}

@available(macOS 14.2, *)
private final class SystemAudioCapture {
  private let callbackQueue = DispatchQueue(
    label: "com.lesserevil.trainee.audio-callback",
    qos: .userInitiated
  )
  private let writer: PCMWriter
  private var tapID = AudioObjectID(kAudioObjectUnknown)
  private var aggregateDeviceID = AudioObjectID(kAudioObjectUnknown)
  private var ioProcID: AudioDeviceIOProcID?
  private var converter: AVAudioConverter?
  private var outputFormat: AVAudioFormat?
  private var isRunning = false

  init(onOutputClosed: @escaping @Sendable () -> Void) {
    writer = PCMWriter(onOutputClosed: onOutputClosed)
  }

  func start() throws {
    let tapDescription = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
    tapDescription.name = "trainee System Audio"
    tapDescription.uuid = UUID()
    tapDescription.isPrivate = true
    tapDescription.muteBehavior = .unmuted

    try checkStatus(
      AudioHardwareCreateProcessTap(tapDescription, &tapID),
      "Creating the system audio process tap"
    )

    var streamDescription = try readTapFormat(tapID)
    guard let inputFormat = AVAudioFormat(streamDescription: &streamDescription) else {
      throw CaptureError(message: "Core Audio returned an unsupported process tap format")
    }
    guard
      let outputFormat = AVAudioFormat(
        commonFormat: .pcmFormatFloat32,
        sampleRate: outputSampleRate,
        channels: 1,
        interleaved: false
      )
    else {
      throw CaptureError(message: "Could not create the 16 kHz mono output format")
    }
    guard let converter = AVAudioConverter(from: inputFormat, to: outputFormat) else {
      throw CaptureError(message: "Could not create the system audio sample-rate converter")
    }
    converter.sampleRateConverterQuality = Int(kAudioConverterQuality_Max)
    self.converter = converter
    self.outputFormat = outputFormat

    let outputDeviceID = try readDefaultOutputDevice()
    let outputDeviceUID = try readDeviceUID(outputDeviceID)
    let aggregateDescription: [String: Any] = [
      kAudioAggregateDeviceNameKey: "trainee Private Audio Capture",
      kAudioAggregateDeviceUIDKey: UUID().uuidString,
      kAudioAggregateDeviceMainSubDeviceKey: outputDeviceUID,
      kAudioAggregateDeviceIsPrivateKey: true,
      kAudioAggregateDeviceIsStackedKey: false,
      kAudioAggregateDeviceTapAutoStartKey: true,
      kAudioAggregateDeviceSubDeviceListKey: [
        [kAudioSubDeviceUIDKey: outputDeviceUID]
      ],
      kAudioAggregateDeviceTapListKey: [
        [
          kAudioSubTapUIDKey: tapDescription.uuid.uuidString,
          kAudioSubTapDriftCompensationKey: true,
        ]
      ],
    ]

    try checkStatus(
      AudioHardwareCreateAggregateDevice(
        aggregateDescription as CFDictionary,
        &aggregateDeviceID
      ),
      "Creating the private tap device"
    )

    try checkStatus(
      AudioDeviceCreateIOProcIDWithBlock(
        &ioProcID,
        aggregateDeviceID,
        callbackQueue
      ) { [weak self] _, inputData, _, _, _ in
        self?.process(inputData, inputFormat: inputFormat)
      },
      "Creating the audio capture callback"
    )
    try checkStatus(
      AudioDeviceStart(aggregateDeviceID, ioProcID),
      "Starting system audio capture"
    )
    isRunning = true
    try writer.markReady()
  }

  func stop() {
    if isRunning, aggregateDeviceID != kAudioObjectUnknown {
      _ = AudioDeviceStop(aggregateDeviceID, ioProcID)
      isRunning = false
    }
    if aggregateDeviceID != kAudioObjectUnknown, let ioProcID {
      _ = AudioDeviceDestroyIOProcID(aggregateDeviceID, ioProcID)
      self.ioProcID = nil
    }
    writer.close()
    if aggregateDeviceID != kAudioObjectUnknown {
      _ = AudioHardwareDestroyAggregateDevice(aggregateDeviceID)
      aggregateDeviceID = AudioObjectID(kAudioObjectUnknown)
    }
    if tapID != kAudioObjectUnknown {
      _ = AudioHardwareDestroyProcessTap(tapID)
      tapID = AudioObjectID(kAudioObjectUnknown)
    }
  }

  private func process(
    _ inputData: UnsafePointer<AudioBufferList>,
    inputFormat: AVAudioFormat
  ) {
    guard isRunning,
      let converter,
      let outputFormat,
      let inputBuffer = AVAudioPCMBuffer(
        pcmFormat: inputFormat,
        bufferListNoCopy: inputData,
        deallocator: nil
      ),
      inputBuffer.frameLength > 0
    else {
      return
    }

    let ratio = outputSampleRate / inputFormat.sampleRate
    let outputCapacity = AVAudioFrameCount(
      ceil(Double(inputBuffer.frameLength) * ratio) + 64
    )
    guard
      let outputBuffer = AVAudioPCMBuffer(
        pcmFormat: outputFormat,
        frameCapacity: outputCapacity
      )
    else {
      return
    }

    var suppliedInput = false
    var conversionError: NSError?
    let status = converter.convert(to: outputBuffer, error: &conversionError) {
      _, inputStatus in
      if suppliedInput {
        inputStatus.pointee = .noDataNow
        return nil
      }
      suppliedInput = true
      inputStatus.pointee = .haveData
      return inputBuffer
    }
    guard status != .error,
      conversionError == nil,
      outputBuffer.frameLength > 0,
      let samples = outputBuffer.floatChannelData?[0]
    else {
      return
    }

    writer.enqueue(
      Data(
        bytes: samples,
        count: Int(outputBuffer.frameLength) * MemoryLayout<Float>.size
      )
    )
  }

  deinit {
    stop()
  }
}

private func writeStandardError(_ message: String) {
  let data = Data(("[audio-helper] \(message)\n").utf8)
  FileHandle.standardError.write(data)
}

if CommandLine.arguments.dropFirst().contains("--self-test") {
  FileHandle.standardOutput.write(Data("trainee audio helper: ok\n".utf8))
  exit(EXIT_SUCCESS)
}

guard #available(macOS 14.2, *) else {
  writeStandardError("native system audio capture requires macOS 14.2 or newer")
  exit(EXIT_FAILURE)
}

signal(SIGPIPE, SIG_IGN)
let stopSemaphore = DispatchSemaphore(value: 0)
private let capture = SystemAudioCapture {
  stopSemaphore.signal()
}
var signalSources: [DispatchSourceSignal] = []

for signalNumber in [SIGINT, SIGTERM] {
  signal(signalNumber, SIG_IGN)
  let source = DispatchSource.makeSignalSource(
    signal: signalNumber,
    queue: DispatchQueue.global(qos: .userInitiated)
  )
  source.setEventHandler {
    stopSemaphore.signal()
  }
  source.resume()
  signalSources.append(source)
}

do {
  try capture.start()
  stopSemaphore.wait()
  capture.stop()
  withExtendedLifetime(signalSources) {}
} catch {
  capture.stop()
  writeStandardError(error.localizedDescription)
  exit(EXIT_FAILURE)
}
