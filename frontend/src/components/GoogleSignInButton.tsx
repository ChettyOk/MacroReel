import { GoogleLogin, type CredentialResponse } from "@react-oauth/google";
import { useEffect, useRef, useState } from "react";

type GoogleSignInButtonProps = {
  text?: "signin_with" | "signup_with";
  disabled?: boolean;
  onSuccess: (response: CredentialResponse) => void;
  onError: () => void;
};

export function GoogleSignInButton({
  text = "signin_with",
  disabled = false,
  onSuccess,
  onError,
}: GoogleSignInButtonProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    const update = () => setWidth(Math.max(200, Math.floor(el.getBoundingClientRect().width)));
    update();

    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    observer?.observe(el);
    window.addEventListener("resize", update);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  return (
    <div ref={wrapRef} className="auth-google__button">
      {width > 0 && !disabled ? (
        <GoogleLogin
          key={`${text}-${width}`}
          onSuccess={onSuccess}
          onError={onError}
          theme="outline"
          size="large"
          width={`${width}`}
          text={text}
          shape="rectangular"
        />
      ) : null}
    </div>
  );
}
