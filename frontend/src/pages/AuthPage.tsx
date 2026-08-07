import { GoogleLogin, type CredentialResponse } from "@react-oauth/google";
import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { SECURITY_QUESTIONS } from "../api";
import { useAuth } from "../context/AuthContext";
import { useRuntimeConfig } from "../context/RuntimeConfigContext";
import * as api from "../api";
import {
  EMAIL_MAX,
  NAME_MAX,
  PASSWORD_MAX,
  PASSWORD_MIN,
  SECURITY_ANSWER_MAX,
  SECURITY_ANSWER_MIN,
  SECURITY_QUESTION_MAX,
  SECURITY_QUESTION_MIN,
  passwordCriteriaMessage,
  validateNewPassword,
  validateSecurityAnswer,
  validateSecurityQuestion,
} from "../lib/authPassword";
import { toUserErrorMessage } from "../lib/userError";

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
  const [confirmRegisterPassword, setConfirmRegisterPassword] = useState("");
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
    setConfirmRegisterPassword("");
    setSecurityAnswer("");
    setPassword("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }

    if (mode === "register") {
      const pwErr = validateNewPassword(password);
      if (pwErr) {
        setError(pwErr);
        return;
      }
      if (password !== confirmRegisterPassword) {
        setError("Passwords do not match.");
        return;
      }
      const qErr = validateSecurityQuestion(securityQuestion);
      if (qErr) {
        setError(qErr);
        return;
      }
      const aErr = validateSecurityAnswer(securityAnswer);
      if (aErr) {
        setError(aErr);
        return;
      }
    } else if (!password) {
      setError("Password is required.");
      return;
    } else if (password.length > PASSWORD_MAX) {
      setError(`Password must be at most ${PASSWORD_MAX} characters.`);
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(trimmedEmail, password);
      } else {
        await register(
          trimmedEmail,
          password,
          securityQuestion,
          securityAnswer.trim(),
          name.trim() || undefined,
        );
      }
    } catch (err) {
      setError(toUserErrorMessage(err, "Sign-in failed. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetLookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      const question = await api.lookupForgotPasswordQuestion(trimmedEmail);
      setResetQuestion(question);
      setResetStep(2);
    } catch (err) {
      setError(toUserErrorMessage(err, "We couldn’t find that account. Check the email and try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const aErr = validateSecurityAnswer(securityAnswer);
    if (aErr) {
      setError(aErr);
      return;
    }
    const pwErr = validateNewPassword(newPassword);
    if (pwErr) {
      setError(pwErr);
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPasswordWithSecurityAnswer(email.trim(), securityAnswer.trim(), newPassword);
      setResetSuccess(true);
      setPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSecurityAnswer("");
    } catch (err) {
      setError(toUserErrorMessage(err, "Password reset failed. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle(response: CredentialResponse) {
    if (!response.credential) {
      setError("Google sign-in did not complete. Please try again.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await loginWithGoogle(response.credential);
    } catch (err) {
      setError(toUserErrorMessage(err, "Google sign-in failed. Please try again."));
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
            {resetSuccess
              ? "Your password was updated."
              : resetStep === 1
                ? "Enter your account email to load your security question."
                : "Answer your security question, then choose a new password."}
          </p>

          {error ? (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          ) : null}

          {resetSuccess ? (
            <>
              <div className="alert alert--success" role="status">
                You can sign in with your new password.
              </div>
              <button type="button" className="btn btn--primary btn--block" onClick={() => switchMode("login")}>
                Sign in
              </button>
            </>
          ) : resetStep === 1 ? (
            <form className="form-stack" onSubmit={handleResetLookup} noValidate>
              <label className="field">
                <span className="field__label">Email</span>
                <input
                  className="input"
                  type="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  maxLength={EMAIL_MAX}
                  placeholder="name@email.com"
                />
              </label>
              <button type="submit" className="btn btn--primary btn--block" disabled={submitting || loading}>
                {submitting ? "Please wait…" : "Continue"}
              </button>
            </form>
          ) : (
            <form className="form-stack" onSubmit={handleResetPassword} noValidate>
              <label className="field">
                <span className="field__label">Security question</span>
                <p className="auth-question">{resetQuestion}</p>
              </label>
              <label className="field">
                <span className="field__label">Your answer</span>
                <input
                  className="input"
                  type="text"
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  required
                  minLength={SECURITY_ANSWER_MIN}
                  maxLength={SECURITY_ANSWER_MAX}
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
                  minLength={PASSWORD_MIN}
                  maxLength={PASSWORD_MAX}
                  placeholder={passwordCriteriaMessage()}
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
                  minLength={PASSWORD_MIN}
                  maxLength={PASSWORD_MAX}
                />
              </label>
              <p className="auth-note">{passwordCriteriaMessage()}</p>
              <button type="submit" className="btn btn--primary btn--block" disabled={submitting || loading}>
                {submitting ? "Please wait…" : "Update password"}
              </button>
            </form>
          )}

          {!resetSuccess ? (
            <p className="auth-switch">
              <button type="button" className="auth-link" onClick={() => switchMode("login")}>
                Back to sign in
              </button>
            </p>
          ) : null}
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
                onError={() => setError("Google sign-in was cancelled or failed. Please try again.")}
                theme="outline"
                size="large"
                width={`${googleWidth}`}
                shape="rectangular"
                text={mode === "login" ? "signin_with" : "signup_with"}
              />
            ) : null}
          </div>
        ) : null}

        {googleClientId ? (
          <div className="auth-divider">
            <span>or</span>
          </div>
        ) : null}

        <form className="form-stack" onSubmit={handleSubmit} noValidate>
          {mode === "register" ? (
            <label className="field">
              <span className="field__label">Name (optional)</span>
              <input
                className="input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                maxLength={NAME_MAX}
                placeholder="Your name"
              />
            </label>
          ) : null}

          <label className="field">
            <span className="field__label">Email</span>
            <input
              className="input"
              type="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              maxLength={EMAIL_MAX}
              placeholder="name@email.com"
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
              minLength={mode === "register" ? PASSWORD_MIN : 1}
              maxLength={PASSWORD_MAX}
              placeholder={mode === "register" ? passwordCriteriaMessage() : "Your password"}
            />
          </label>

          {mode === "register" ? (
            <>
              <label className="field">
                <span className="field__label">Confirm password</span>
                <input
                  className="input"
                  type="password"
                  value={confirmRegisterPassword}
                  onChange={(e) => setConfirmRegisterPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  minLength={PASSWORD_MIN}
                  maxLength={PASSWORD_MAX}
                />
              </label>
              <p className="auth-note">{passwordCriteriaMessage()}</p>
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
                    type="text"
                    value={customQuestion}
                    onChange={(e) => setCustomQuestion(e.target.value)}
                    required
                    minLength={SECURITY_QUESTION_MIN}
                    maxLength={SECURITY_QUESTION_MAX}
                    placeholder="e.g. Favorite childhood nickname?"
                  />
                </label>
              ) : null}
              <label className="field">
                <span className="field__label">Security answer</span>
                <input
                  className="input"
                  type="text"
                  value={securityAnswer}
                  onChange={(e) => setSecurityAnswer(e.target.value)}
                  required
                  minLength={SECURITY_ANSWER_MIN}
                  maxLength={SECURITY_ANSWER_MAX}
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
