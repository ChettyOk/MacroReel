import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {
    private let appGroupId = "group.com.chettyok.macroreel"
    private let sharedTextKey = "macroreel.sharedText"

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        extractSharedText { [weak self] sharedText in
            guard let self else { return }
            let cleaned = sharedText?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if !cleaned.isEmpty {
                UserDefaults(suiteName: self.appGroupId)?.set(cleaned, forKey: self.sharedTextKey)
            }
            self.openMacroReel(with: cleaned)
        }
    }

    private func extractSharedText(completion: @escaping (String?) -> Void) {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            completion(nil)
            return
        }

        let providers = items.flatMap { $0.attachments ?? [] }
        if providers.isEmpty {
            completion(items.compactMap { $0.attributedContentText?.string }.joined(separator: " ").nilIfEmpty())
            return
        }

        let typeOrder: [String] = [
            UTType.url.identifier,
            UTType.plainText.identifier,
            UTType.text.identifier,
            UTType.fileURL.identifier,
            UTType.movie.identifier,
            UTType.image.identifier,
        ]

        for typeId in typeOrder {
            if let provider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(typeId) }) {
                provider.loadItem(forTypeIdentifier: typeId, options: nil) { item, _ in
                    if let url = item as? URL {
                        completion(url.absoluteString)
                    } else if let text = item as? String {
                        completion(text)
                    } else if let data = item as? Data, let text = String(data: data, encoding: .utf8) {
                        completion(text)
                    } else {
                        completion(nil)
                    }
                }
                return
            }
        }

        completion(nil)
    }

    private func openMacroReel(with sharedText: String) {
        let encoded = sharedText.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let urlString = encoded.isEmpty ? "macroreel://import" : "macroreel://import?url=\(encoded)"
        guard let url = URL(string: urlString) else {
            extensionContext?.completeRequest(returningItems: nil)
            return
        }

        DispatchQueue.main.async { [weak self] in
            self?.launchHostApp(url: url)
            self?.extensionContext?.completeRequest(returningItems: nil)
        }
    }

    /// Open the host app from a Share Extension. `extensionContext.open` is not
    /// reliable for share extensions, so walk the responder chain to `openURL:`.
    private func launchHostApp(url: URL) {
        var responder: UIResponder? = self
        let selector = NSSelectorFromString("openURL:")
        while let current = responder {
            if current.responds(to: selector) {
                _ = current.perform(selector, with: url)
                return
            }
            responder = current.next
        }
        // Fallback: try the extension context API as a last resort.
        extensionContext?.open(url, completionHandler: nil)
    }
}

private extension String {
    func nilIfEmpty() -> String? {
        isEmpty ? nil : self
    }
}
