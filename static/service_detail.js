const openConsultButtons = document.querySelectorAll("[data-open-consult-popup]");
const consultModal = document.querySelector("[data-consult-modal]");
const closeConsultButtons = document.querySelectorAll("[data-close-consult-modal]");
const consultForm = document.querySelector("[data-consult-form]");
const consultStatus = document.querySelector("[data-consult-status]");

function toggleConsultModal(show) {
  if (!consultModal) return;
  consultModal.classList.toggle("hidden", !show);
  document.body.style.overflow = show ? "hidden" : "";
}

openConsultButtons.forEach((btn) => {
  btn.addEventListener("click", () => toggleConsultModal(true));
});
closeConsultButtons.forEach((button) => {
  button.addEventListener("click", () => toggleConsultModal(false));
});

if (consultForm) {
  consultForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (consultStatus) consultStatus.textContent = "Đang gửi thông tin...";

    const payload = Object.fromEntries(new FormData(consultForm).entries());

    try {
      const response = await fetch("/api/consultations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.error || "Gửi thông tin thất bại");
      }

      if (consultStatus) {
        consultStatus.textContent = "Đã gửi thành công. Chúng tôi sẽ liên hệ với bạn sớm nhất.";
      }
      consultForm.reset();
    } catch (error) {
      const err = error instanceof Error ? error.message : String(error);
      if (consultStatus) consultStatus.textContent = `Lỗi: ${err}`;
    }
  });
}
