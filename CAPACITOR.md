# Build MacroReel With Capacitor

Capacitor wraps the React app in a native Android/iOS shell. The app UI is bundled into the native app, while the FastAPI backend should stay deployed on Render.

## 1. Deploy The Backend First

Deploy MacroReel on Render and confirm these URLs work:

```bash
https://your-macroreel-service.onrender.com/health
https://your-macroreel-service.onrender.com
```

The mobile app must call the Render URL, not `localhost`.

## 2. Configure The Mobile API URL

Create a local Capacitor env file:

```bash
cd frontend
cp .env.capacitor.example .env.capacitor
```

Edit `frontend/.env.capacitor`:

```env
VITE_API_URL=https://your-macroreel-service.onrender.com
```

Do not commit `.env.capacitor`.

## 3. Install Native Tooling

Android:

- Install Android Studio.
- Open Android Studio once and install the recommended SDK/platform tools.

iOS:

- Install Xcode from the Mac App Store.
- Open Xcode once and accept the license/install prompts.

You only need Xcode for iPhone/iPad builds. You only need Android Studio for Android builds.

## 4. Add Native Projects

Run this once:

```bash
cd frontend
npm install
npm run build:capacitor
npm run cap:add:android
npm run cap:add:ios
```

If `android/` or `ios/` already exists, skip the matching `npm run cap:add:...` command.

## 5. Sync After Every Web Change

Any time you change React/CSS/API code:

```bash
cd frontend
npm run cap:build
```

This builds the Vite app with `.env.capacitor` and copies it into Android/iOS.

## 6. Open And Run

Android:

```bash
cd frontend
npm run cap:open:android
```

Then press Run in Android Studio.

iOS:

```bash
cd frontend
npm run cap:open:ios
```

Then select a simulator/device in Xcode and press Run.

## 7. App Store Notes

- Bundle id: `com.chettyok.macroreel`
- App name: `MacroReel`
- Backend CORS already allows Capacitor origins.
- For production store releases, create proper PNG app icons and splash assets in Android Studio/Xcode.
- Android native share receive is wired for text shares and TikTok/Instagram/YouTube links. Shared text opens MacroReel at `/import` with the shared URL prefilled.
- iOS native share receive is wired through the `MacroReelShareExtension` target. Shared text/URLs are saved through the App Group `group.com.chettyok.macroreel`, then the main app opens `/import`.

## 8. iOS Share Extension Setup

The repo includes the extension target, but Apple requires App Groups to be enabled on your real signing team:

1. Open `frontend/ios/App/App.xcodeproj` in Xcode.
2. Select the **App** target, then **Signing & Capabilities**.
3. Add **App Groups** and enable:

```text
group.com.chettyok.macroreel
```

4. Select the **MacroReelShareExtension** target and enable the same App Group.
5. Make sure both targets use your Apple Developer Team.
6. Run the app on a simulator/device, share a TikTok/Instagram/YouTube link, and choose **MacroReel**.

If Xcode says the App Group is unavailable, create it in the Apple Developer portal first for both bundle IDs:

```text
com.chettyok.macroreel
com.chettyok.macroreel.ShareExtension
```
