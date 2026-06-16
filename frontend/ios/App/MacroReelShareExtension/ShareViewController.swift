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
            self.openMacroReel()
        }
    }

    private func extractSharedText(completion: @escaping (String?) -> Void) {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            completion(nil)
            return
        }

        let providers = items.flatMap { $0.attachments ?? [] }
        if providers.isEmpty {
            completion(nil)
            return
        }

        if let urlProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.url.identifier) }) {
            urlProvider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { item, _ in
                if let url = item as? URL {
                    completion(url.absoluteString)
                } else if let text = item as? String {
                    completion(text)
                } else {
                    completion(nil)
                }
            }
            return
        }

        if let textProvider = providers.first(where: { $0.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) }) {
            textProvider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { item, _ in
                completion(item as? String)
            }
            return
        }

        completion(nil)
    }

    private func openMacroReel() {
        DispatchQueue.main.async {
            guard let url = URL(string: "macroreel://import") else {
                self.extensionContext?.completeRequest(returningItems: nil)
                return
            }

            var responder: UIResponder? = self
            let selector = NSSelectorFromString("openURL:")
            while let current = responder {
                if current.responds(to: selector) {
                    _ = current.perform(selector, with: url)
                    break
                }
                responder = current.next
            }

            self.extensionContext?.completeRequest(returningItems: nil)
        }
    }
}
