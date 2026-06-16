import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.chettyok.macroreel",
  appName: "MacroReel",
  webDir: "dist",
  bundledWebRuntime: false,
  server: {
    androidScheme: "https",
    iosScheme: "capacitor",
  },
};

export default config;
