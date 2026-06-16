import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import "./index.css";
import { CartPage } from "./pages/CartPage";
import { CookbookPage } from "./pages/CookbookPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { HomePage } from "./pages/HomePage";
import { ImportPage } from "./pages/ImportPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RecipeDetailPage } from "./pages/RecipeDetailPage";
import { RecipeFormPage } from "./pages/RecipeFormPage";
import { clearStaleClientCache } from "./lib/storage";

clearStaleClientCache();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Navigate to="/home" replace />} />
          <Route path="home" element={<HomePage />} />
          <Route path="discover" element={<DiscoverPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="cookbook" element={<CookbookPage />} />
          <Route path="cart" element={<CartPage />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="new" element={<RecipeFormPage />} />
          <Route path="edit/:id" element={<RecipeFormPage />} />
          <Route path="recipe/:id" element={<RecipeDetailPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
