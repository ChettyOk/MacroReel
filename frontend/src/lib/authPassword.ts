/** Shared password rules for register / reset (aligned with backend). */

export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;
export const EMAIL_MAX = 320;
export const NAME_MAX = 200;
export const SECURITY_QUESTION_MIN = 3;
export const SECURITY_QUESTION_MAX = 300;
export const SECURITY_ANSWER_MIN = 2;
export const SECURITY_ANSWER_MAX = 200;

const HAS_LETTER = /[A-Za-z]/;
const HAS_DIGIT = /\d/;

export function passwordMeetsCriteria(password: string): boolean {
  if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) return false;
  return HAS_LETTER.test(password) && HAS_DIGIT.test(password);
}

/** User-facing message when a new password fails criteria. */
export function passwordCriteriaMessage(): string {
  return `Password must be ${PASSWORD_MIN}–${PASSWORD_MAX} characters and include at least one letter and one number.`;
}

export function validateNewPassword(password: string): string | null {
  if (!password) return "Password is required";
  if (password.length < PASSWORD_MIN) return `Password must be at least ${PASSWORD_MIN} characters.`;
  if (password.length > PASSWORD_MAX) return `Password must be at most ${PASSWORD_MAX} characters.`;
  if (!HAS_LETTER.test(password) || !HAS_DIGIT.test(password)) {
    return passwordCriteriaMessage();
  }
  return null;
}

export function validateSecurityAnswer(answer: string): string | null {
  const trimmed = answer.trim();
  if (trimmed.length < SECURITY_ANSWER_MIN) {
    return `Security answer must be at least ${SECURITY_ANSWER_MIN} characters.`;
  }
  if (trimmed.length > SECURITY_ANSWER_MAX) {
    return `Security answer must be at most ${SECURITY_ANSWER_MAX} characters.`;
  }
  return null;
}

export function validateSecurityQuestion(question: string): string | null {
  const trimmed = question.trim();
  if (trimmed.length < SECURITY_QUESTION_MIN) {
    return "Choose or write a security question.";
  }
  if (trimmed.length > SECURITY_QUESTION_MAX) {
    return `Security question must be at most ${SECURITY_QUESTION_MAX} characters.`;
  }
  return null;
}
