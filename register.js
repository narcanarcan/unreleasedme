const form = document.querySelector("#register-form");
const usernameInput = document.querySelector("#username");
const emailInput = document.querySelector("#register-email");
const passwordInput = document.querySelector("#register-password");
const confirmPasswordInput = document.querySelector("#confirm-password");
const inviteCodeInput = document.querySelector("#invite-code");
const statusMessage = document.querySelector(".form-status");
const inputs = [usernameInput, emailInput, passwordInput, confirmPasswordInput, inviteCodeInput];

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
  let isValid = input.validity.valid && input.value.trim().length > 0;
  if (input === confirmPasswordInput) {
    isValid = isValid && input.value === passwordInput.value;
  }
  setFieldState(input, isValid);
  return isValid;
}

inputs.forEach((input) => {
  input.addEventListener("blur", () => validateInput(input));
  input.addEventListener("input", () => {
    if (input.closest(".field").classList.contains("invalid")) {
      validateInput(input);
    }
    if (input === passwordInput && confirmPasswordInput.value) {
      validateInput(confirmPasswordInput);
    }
    statusMessage.textContent = "";
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const isValid = inputs.map(validateInput).every(Boolean);
  if (!isValid) {
    form.querySelector("[aria-invalid='true']")?.focus();
    statusMessage.textContent = "Please check the highlighted fields.";
    return;
  }

  const submitButton = form.querySelector("button[type='submit']");
  submitButton.disabled = true;
  statusMessage.textContent = "Creating your account...";

  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameInput.value.trim(),
        email: emailInput.value.trim(),
        password: passwordInput.value,
        inviteCode: inviteCodeInput.value.trim(),
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Registration failed.");
    }
    statusMessage.textContent = "Account created. Opening your profile...";
    window.setTimeout(() => {
      window.location.href = "account.html";
    }, 500);
  } catch (error) {
    statusMessage.textContent = error.message;
    submitButton.disabled = false;
  }
});
