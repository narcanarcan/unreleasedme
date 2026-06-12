const form = document.querySelector("#login-form");
const emailInput = document.querySelector("#email");
const passwordInput = document.querySelector("#password");
const passwordToggle = document.querySelector(".password-toggle");
const statusMessage = document.querySelector(".form-status");

function setFieldState(input, isValid) {
  input.closest(".field").classList.toggle("invalid", !isValid);
  input.setAttribute("aria-invalid", String(!isValid));
  if (isValid) {
    input.removeAttribute("aria-describedby");
  } else {
    input.setAttribute("aria-describedby", `${input.id}-error`);
  }
}

function validateInput(input) {
  const isValid = input.validity.valid;
  setFieldState(input, isValid);
  return isValid;
}

passwordToggle.addEventListener("click", () => {
  const showingPassword = passwordInput.type === "text";
  passwordInput.type = showingPassword ? "password" : "text";
  passwordToggle.setAttribute("aria-pressed", String(!showingPassword));
  passwordToggle.setAttribute("aria-label", showingPassword ? "Show password" : "Hide password");
});

[emailInput, passwordInput].forEach((input) => {
  input.addEventListener("blur", () => validateInput(input));
  input.addEventListener("input", () => {
    if (input.closest(".field").classList.contains("invalid")) {
      validateInput(input);
    }
    statusMessage.textContent = "";
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const isValid = [emailInput, passwordInput].map(validateInput).every(Boolean);
  if (!isValid) {
    form.querySelector("[aria-invalid='true']")?.focus();
    statusMessage.textContent = "Please check the highlighted fields.";
    return;
  }

  const submitButton = form.querySelector("button[type='submit']");
  submitButton.disabled = true;
  statusMessage.textContent = "Signing in...";

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: emailInput.value.trim(),
        password: passwordInput.value,
        remember: form.elements.remember.checked,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Sign in failed.");
    }
    window.location.href = "home.html";
  } catch (error) {
    statusMessage.textContent = error.message;
    submitButton.disabled = false;
  }
});
