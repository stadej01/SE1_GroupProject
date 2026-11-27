const email = document.querySelector('input[name="email"]');
const suggestions = document.querySelector(".teammate-suggestions");
if (suggestions) {
  suggestions.hidden = false;
  suggestions.addEventListener("click", event => {
    const button = event.target.closest("button[data-member-email]");
    if (!button) return;
    email.value = button.dataset.memberEmail;
    email.dispatchEvent(new Event("input"));
    email.focus();
  });
}

for (const notice of document.querySelectorAll("[data-highlight]")) {
  const row = document.getElementById(notice.dataset.highlight);
  if (row) {
    row.classList.add("new-member");
    setTimeout(() => row.classList.remove("new-member"), 2000);
  }
}

const signup = document.getElementById("signup-help");
if (signup) {
  const link = document.getElementById("signup-link");
  const copy = document.getElementById("copy-signup");
  const manual = document.getElementById("signup-manual");
  const input = document.getElementById("signup-url");
  link.hidden = true;
  copy.hidden = false;
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(link.href);
      manual.hidden = true;
      document.getElementById("signup-feedback").textContent = "Link copied.";
    } catch {
      document.getElementById("signup-feedback").textContent = "";
      manual.hidden = false;
      input.value = link.href;
      input.select();
    }
  });
}

if (email.hasAttribute("aria-invalid")) {
  email.addEventListener("input", () => {
    document.getElementById(email.id + "_error").hidden = true;
    email.removeAttribute("aria-invalid");
    email.removeAttribute("aria-describedby");
    if (signup) signup.hidden = true;
  }, { once: true });
}
