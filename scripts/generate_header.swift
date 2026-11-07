// Run from the repository root: swift scripts/generate_header.swift
import AppKit
import ImageIO
import UniformTypeIdentifiers

let width = 1000
let height = 300
let frameCount = 48
let output = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("assets")
guard let illustration = NSImage(contentsOf: output.appendingPathComponent("illustration.png")) else {
    fatalError("Run from the repository root with assets/illustration.png present")
}
let background = NSColor(srgbRed: 0.055, green: 0.067, blue: 0.086, alpha: 1)
let ink = NSColor(srgbRed: 0.92, green: 0.93, blue: 0.91, alpha: 1)
let muted = NSColor(srgbRed: 0.55, green: 0.60, blue: 0.65, alpha: 1)
let accent = NSColor(srgbRed: 0.93, green: 0.47, blue: 0.34, alpha: 1)


func render(_ frame: Int) -> CGImage {
    let bitmap = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: width, pixelsHigh: height,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
        isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    )!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)!
    defer { NSGraphicsContext.restoreGraphicsState() }

    func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat, _ color: NSColor) {
        color.setFill()
        NSRect(x: x, y: CGFloat(height) - y - h, width: w, height: h).fill()
    }
    func text(_ value: String, _ x: CGFloat, _ y: CGFloat, _ size: CGFloat,
              _ color: NSColor, bold: Bool = false) {
        let font = NSFont.monospacedSystemFont(ofSize: size, weight: bold ? .semibold : .regular)
        (value as NSString).draw(
            at: NSPoint(x: x, y: CGFloat(height) - y - font.ascender),
            withAttributes: [.font: font, .foregroundColor: color]
        )
    }

    rect(0, 0, CGFloat(width), CGFloat(height), background)
    rect(0, 0, 5, CGFloat(height), accent)
    illustration.draw(in: NSRect(x: 650, y: 0, width: 300, height: 300))
    rect(42, 62, 550, 1, muted.withAlphaComponent(0.22))
    text("~/Rishi", 42, 26, 14, muted)
    for (index, character) in "Rishi".enumerated() {
        let progress = min(1.0, max(0.0, (Double(frame) - Double(index) * 3) / 18))
        let eased = 1 - pow(1 - progress, 3)
        let y = 86 + CGFloat(1 - eased) * 26
        text(String(character), 40 + CGFloat(index) * 43, y, 72,
             ink.withAlphaComponent(CGFloat(eased)), bold: true)

    }
    text("backend / developer tools / applied AI", 43, 167, 17, muted)
    let lineProgress = min(1.0, Double(frame) / 30)
    rect(43, 211, 34 + CGFloat(lineProgress) * 176, 3, accent)
    text("Rutgers University", 43, 248, 13, ink)
    text("New Brunswick, NJ", 243, 248, 13, muted)

    return bitmap.cgImage!
}

try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let gifURL = output.appendingPathComponent("rishi-name-reveal.gif")
let pngURL = output.appendingPathComponent("rishi-header-still.png")
guard let gif = CGImageDestinationCreateWithURL(gifURL as CFURL, UTType.gif.identifier as CFString, frameCount, nil),
      let png = CGImageDestinationCreateWithURL(pngURL as CFURL, UTType.png.identifier as CFString, 1, nil) else {
    fatalError("Could not create image files")
}
CGImageDestinationSetProperties(gif, [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFLoopCount: 0]] as CFDictionary)
for frame in 0..<frameCount {
    let image = render(frame)
    let delay = frame == frameCount - 1 ? 4.0 : 0.04
    CGImageDestinationAddImage(gif, image, [
        kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFDelayTime: delay]
    ] as CFDictionary)
    if frame == frameCount - 1 { CGImageDestinationAddImage(png, image, nil) }
}
guard CGImageDestinationFinalize(gif), CGImageDestinationFinalize(png) else {
    fatalError("Could not finish writing header images")
}

// Check the name changes between encoded frames and holds on the complete name.
guard let decoded = CGImageSourceCreateWithURL(gifURL as CFURL, nil),
      let still = CGImageSourceCreateWithURL(pngURL as CFURL, nil),
      let last = CGImageSourceCreateImageAtIndex(decoded, frameCount - 1, nil),
      let first = CGImageSourceCreateImageAtIndex(decoded, 0, nil),
      let firstName = first.cropping(to: CGRect(x: 210, y: 80, width: 50, height: 84)),
      let lastName = last.cropping(to: CGRect(x: 210, y: 80, width: 50, height: 84)),
      let firstPixels = NSBitmapImageRep(cgImage: firstName).representation(using: .png, properties: [:]),
      let lastPixels = NSBitmapImageRep(cgImage: lastName).representation(using: .png, properties: [:]),
      let stillImage = CGImageSourceCreateImageAtIndex(still, 0, nil),
      let properties = CGImageSourceCopyPropertiesAtIndex(decoded, frameCount - 1, nil) as? [String: Any],
      let gifProperties = properties[kCGImagePropertyGIFDictionary as String] as? [String: Any],
      let delay = gifProperties[kCGImagePropertyGIFDelayTime as String] as? Double else {
    fatalError("Generated images could not be decoded")
}
precondition(CGImageSourceGetCount(decoded) == frameCount)
precondition(last.width == width && last.height == height)
precondition(stillImage.width == width && stillImage.height == height)
precondition(delay >= 4)
precondition(firstPixels != lastPixels)
print("Generated and verified \(frameCount)-frame GIF and reduced-motion PNG (\(width)x\(height)).")
