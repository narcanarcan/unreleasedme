const emailButton = document.querySelector(".contact-button--email");
const emailDisplay = document.querySelector("#contact-email-display");

emailButton.addEventListener("click", () => {
  const willShow = emailDisplay.hidden;
  emailDisplay.hidden = !willShow;
  emailButton.setAttribute("aria-expanded", String(willShow));
  emailButton.classList.toggle("is-active", willShow);

  if (willShow) {
    emailDisplay.querySelector("a").focus();
  }
});
