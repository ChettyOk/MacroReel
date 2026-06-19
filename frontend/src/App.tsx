import { useEffect, useRef } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { setUnauthorizedHandler } from "./api";
import { BottomNav } from "./components/BottomNav";
import { CartHeaderButton } from "./components/CartHeaderButton";
import { useAuth } from "./context/AuthContext";
import { FavoritesProvider } from "./context/FavoritesContext";
import { ShoppingCartProvider } from "./context/ShoppingCartContext";
import { setupNativeImportListener } from "./lib/nativeImport";
import { isOnboardingDone } from "./lib/storage";
import { extractVideoUrlFromText } from "./lib/videoUrl";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const redirectedRef = useRef(false);
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  useEffect(() => {
    if (loading) return;
    if (!user && location.pathname !== "/login") {
      const redirectTo = `${location.pathname}${location.search}`;
      navigate("/login", { replace: true, state: { from: redirectTo } });
      return;
    }
    if (user && !isOnboardingDone(user.id) && !location.pathname.startsWith("/onboarding")) {
      navigate("/onboarding", { replace: true });
    }
  }, [user, loading, location.pathname, location.search, navigate]);

  useEffect(() => {
    return setupNativeImportListener(navigate);
  }, [navigate]);

  useEffect(() => {
    if (redirectedRef.current || !user) return;
    const params = new URLSearchParams(location.search);
    const shared = [params.get("url"), params.get("text"), params.get("title")].filter(Boolean).join(" ");
    const videoUrl = extractVideoUrlFromText(shared);
    if (videoUrl && (location.pathname === "/" || location.pathname === "/home")) {
      redirectedRef.current = true;
      navigate(`/import?url=${encodeURIComponent(videoUrl)}`, { replace: true });
    }
  }, [location, navigate, user]);

  if (loading) {
    return (
      <div className="app-shell app-shell--full">
        <p className="page-sub" style={{ padding: "2rem", textAlign: "center" }}>
          Loading…
        </p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const fullBleed = location.pathname.startsWith("/onboarding");
  const hideNav = location.pathname.startsWith("/onboarding");
  const showCartButton =
    !hideNav && !location.pathname.startsWith("/profile") && !location.pathname.startsWith("/cart");

  return (
    <FavoritesProvider>
      <ShoppingCartProvider>
        <div className={fullBleed ? "app-shell app-shell--full" : "app-shell"}>
          {showCartButton ? <CartHeaderButton /> : null}
          <Outlet />
        </div>
        {!hideNav ? <BottomNav /> : null}
      </ShoppingCartProvider>
    </FavoritesProvider>
  );
}
