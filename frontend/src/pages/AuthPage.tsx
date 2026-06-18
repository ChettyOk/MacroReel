import { GoogleLogin, type CredentialResponse } from "@react-oauth/google";
import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { SECURITY_QUESTIONS } from "../api";
import { useAuth } from "../context/AuthContext";
import { useRuntimeConfig } from "../context/RuntimeConfigContext";
import * as api from "../api";

type Mode = "login" | "register" | "reset";

const CUSTOM_QUESTION = "Write your own question";

export function AuthPage() {
  const { user, loading, login, register, loginWithGoogle } = useAuth();
  const { googleClientId } = useRuntimeConfig();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("login");
  const [resetStep, setResetStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [questionPreset, setQuestionPreset] = useState<string>(SECURITY_QUESTIONS[0]);
  const [customQuestion, setCustomQuestion] = useState("");
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [resetQuestion, setResetQuestion] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetSuccess, setResetSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const googleRef = useRef<HTMLDivElement>(null);
  const [googleWidth, setGoogleWidth] = useState(0);

  const from = (location.state as { from?: string } | null)?.from ?? "/home";

  const securityQuestion =
    questionPreset === CUSTOM_QUESTION ? customQuestion.trim() : questionPreset;

  useEffect(() => {
    const el = googleRef.current;
    if (!el) return;
    const measure = () => setGoogleWidth(Math.max(240, Math.floor(el.getBoundingClientRect().width)));
    measure();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    observer?.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [mode]);

  if (!loading && user) {
    return <Navigate to={from} replace />;
  }

  function switchMode(next: Mode) {
    setMode(next);
    setResetStep(1);
    setError(null);
    setResetSuccess(false);
    setResetQuestion("");
    setNewPassword("");
    setConfirmPassword("");
    setSecurityAnswer("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else if (mode === "register") {
        if (!securityQuestion || securityQuestion.length < 3) {
          throw new Error("Choose or write a security question");
        }
        if (!securityAnswer.trim()) {
          throw new Error("Security answer is required");
        }
        await register(email, password, securityQuestion, securityAnswer.trim(), name.trim() || undefined);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetLookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const question = await api.lookupForgotPasswordQuestion(email.trim());
      setResetQuestion(question);
      setResetStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not find account");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPasswordWithSecurityAnswer(email.trim(), securityAnswer.trim(), newPassword);
      setResetSuccess(true);
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle(response: CredentialResponse) {
    if (!response.credential) {
      setError("Google sign-in did not return a token");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await loginWithGoogle(response.credential);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (mode === "reset") {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <p className="auth-kicker">MacroReel</p>
          <h1 className="auth-title">Reset password</h1>
          <p className="auth-sub">
            {resetStep === 1
              ? "Enter your account email to load your security question."
              : "Answer your security question, then choose a new password."}
          </p>

          {error ? (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          ) : null}

          {resetSuccess ? (
            <div className="alert alert--success" role="status">
              Password updated. You can sign in with your new password.
            </div>
          ) : null}

          {resetStep === 1 ? (
            <form className="form-stack" onSubmit={handleResetLookup}>
              <label className="field">
                <span className="field__label">Email</span>
                <input
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  placeholder="you@example.com"
                />
              </label>
              <button type="submit" className="btn btn--primary btn--block" disabled={submitting || loading}>
                {submitting ? "Please wait…" : "Continue"}
              </button>
            </form>
          ) : (
            <form className="form-stack" onSubmit={handleResetPassword}>
              <label className="field">
                <span className="field__label">Security question</span>
                <p className="auth-question">{resetQuestion}</p>
              </label>
              <label className="field">
                <span className="field__label">Your answer</span>
                <input
                  className="input"
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  required
                  autoComplete="off"
                />
              </label>
              <label className="field">
                <span className="field__label">New password</span>
                <input
                  className="input"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  minLength={8}
                />
              </label>
              <label className="field">
                <span className="field__label">Confirm new password</span>
                <input
                  className="input"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  minLength={8}
                />
              </label>
              <button type="submit" className="btn btn--primary btn--block" disabled={submitting || loading}>
                {submitting ? "Please wait…" : "Update password"}
              </button>
            </form>
          )}

          <p className="auth-switch">
            <button type="button" className="auth-link" onClick={() => switchMode("login")}>
              Back to sign in
            </button>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <p className="auth-kicker">MacroReel</p>
        <h1 className="auth-title">{mode === "login" ? "Sign in" : "Create account"}</h1>
        <p className="auth-sub">
          {mode === "login"
            ? "Your recipes, profile, and meal log stay private to your account."
            : "Pick a security question so you can reset your password without email."}
        </p>

        {error ? (
          <div className="alert alert--error" role="alert">
            {error}
          </div>
        ) : null}

        {googleClientId ? (
          <div className="auth-google" ref={googleRef}>
            {googleWidth > 0 ? (
              <GoogleLogin
                onSuccess={handleGoogle}
                onError={() => setError("Google sign-in was cancelled or failed")}
                theme="outline"
                size="large"
                width={`${googleWidth}`}
                shape="rectangular"
                text={mode === "login" ? "signin_with" : "signup_with"}
              />
            ) : null}
          </div>
        ) : (
          <p className="auth-note">Google sign-in is not configured for this build.</p>
        )}

        <div className="auth-divider">
          <span>or</span>
        </div>

        <form className="form-stack" onSubmit={handleSubmit}>
          {mode === "register" ? (
            <label className="field">
              <span className="field__label">Name (optional)</span>
              <input
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                placeholder="Your name"
              />
            </label>
          ) : null}

          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              placeholder="you@example.com"
            />
          </label>

          <label className="field">
            <span className="field__label">Password</span>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={8}
              placeholder={mode === "register" ? "At least 8 characters" : "Your password"}
            />
          </label>

          {mode === "register" ? (
            <>
              <label className="field">
                <span className="field__label">Security question</span>
                <select
                  className="select"
                  value={questionPreset}
                  onChange={(e) => setQuestionPreset(e.target.value)}
                >
                  {SECURITY_QUESTIONS.map((q) => (
                    <option key={q} value={q}>
                      {q}
                    </option>
                  ))}
                  <option value={CUSTOM_QUESTION}>{CUSTOM_QUESTION}</option>
                </select>
              </label>
              {questionPreset === CUSTOM_QUESTION ? (
                <label className="field">
                  <span className="field__label">Your question</span>
                  <input
                    className="input"
                    value={customQuestion}
                    onChange={(e) => setCustomQuestion(e.target.value)}
                    required
                    placeholder="e.g. Favorite childhood nickname?"
                  />
                </label>
              ) : null}
              <label className="field">
                <span className="field__label">Security answer</span>
                <input
                  className="input"
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  required
                  autoComplete="off"
                  placeholder="Answer you'll remember"
                />
              </label>
            </>
          ) : null}

          <button type="submit" className="btn btn--primary btn--block" disabled={submitting || loading}>
            {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        {mode === "login" ? (
          <p className="auth-switch">
            <button type="button" className="auth-link" onClick={() => switchMode("reset")}>
              Forgot password?
            </button>
          </p>
        ) : null}

        <p className="auth-switch">
          {mode === "login" ? "New here?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="auth-link"
            onClick={() => switchMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}
