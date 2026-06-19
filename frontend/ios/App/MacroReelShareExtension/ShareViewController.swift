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

        extensionContext?.open(url, completionHandler: { [weak self] _ in
            self?.extensionContext?.completeRequest(returningItems: nil)
        })
    }
}

private extension String {
    func nilIfEmpty() -> String? {
        isEmpty ? nil : self
    }
}
