const form = document.querySelector("#edit-profile-form");
const usernameInput = document.querySelector("#edit-username");
const emailInput = document.querySelector("#edit-email");
const inviteCodeInput = document.querySelector("#edit-invite-code");
const profileInput = document.querySelector("#profile-picture");
const profilePreview = document.querySelector("#profile-preview");
const removeProfileButton = document.querySelector("#remove-profile-picture");
const statusMessage = document.querySelector(".form-status");
const inputs = [usernameInput, emailInput];
let pendingProfileImage = null;
let removeProfileImage = false;

function validateInput(input) {
  const isValid = input.validity.valid && input.value.trim().length > 0;
  input.closest(".field").classList.toggle("invalid", !isValid);
  input.setAttribute("aria-invalid", String(!isValid));
  if (isValid) {
    input.removeAttribute("aria-describedby");
  } else {
    input.setAttribute("aria-describedby", `${input.id}-error`);
  }
  return isValid;
}

async function loadProfile() {
  const response = await fetch("/api/me");
  if (response.status === 401) {
    window.location.href = "login.html";
    return;
  }
  const result = await response.json();
  if (!response.ok) {
    statusMessage.textContent = result.error || "Unable to load your profile.";
    return;
  }
  usernameInput.value = result.user.username;
  emailInput.value = result.user.email;
  inviteCodeInput.value = result.user.inviteCode;
  profilePreview.src = result.user.profileImageUrl;
}

inputs.forEach((input) => {
  input.addEventListener("blur", () => validateInput(input));
  input.addEventListener("input", () => {
    if (input.closest(".field").classList.contains("invalid")) {
      validateInput(input);
    }
    statusMessage.textContent = "";
  });
});

profileInput.addEventListener("change", () => {
  const file = profileInput.files[0];
  if (!file) return;
  const supportedTypes = ["image/png", "image/jpeg", "image/gif", "image/webp"];
  if (!supportedTypes.includes(file.type)) {
    statusMessage.textContent = "Choose a PNG, JPEG, GIF, or WebP image.";
    profileInput.value = "";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    statusMessage.textContent = "Profile picture must be 2 MB or smaller.";
    profileInput.value = "";
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    pendingProfileImage = reader.result;
    removeProfileImage = false;
    profilePreview.src = reader.result;
    statusMessage.textContent = "New profile picture selected.";
  });
  reader.readAsDataURL(file);
});

removeProfileButton.addEventListener("click", () => {
  pendingProfileImage = null;
  removeProfileImage = true;
  profileInput.value = "";
  profilePreview.src = "assets/default-profile.png";
  statusMessage.textContent = "The default profile picture will be restored when you save.";
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
  statusMessage.textContent = "Saving your profile...";

  try {
    const response = await fetch("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameInput.value.trim(),
        email: emailInput.value.trim(),
        profileImage: pendingProfileImage,
        removeProfileImage,
      }),
    });
    const result = await response.json();
    if (response.status === 401) {
      window.location.href = "login.html";
      return;
    }
    if (!response.ok) {
      throw new Error(result.error || "Unable to save your profile.");
    }
    statusMessage.textContent = "Profile saved. Returning to your account...";
    window.setTimeout(() => {
      window.location.href = "account.html";
    }, 500);
  } catch (error) {
    statusMessage.textContent = error.message;
    submitButton.disabled = false;
  }
});

loadProfile().catch(() => {
  statusMessage.textContent = "Unable to connect to the account server.";
});
