const clockWidgets = document.querySelectorAll(".clock-widget");

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

function updateClocks() {
  const now = new Date();
  const displayTime = timeFormatter.format(now);
  const seconds = now.getSeconds();
  const minutes = now.getMinutes() + seconds / 60;
  const hours = (now.getHours() % 12) + minutes / 60;

  clockWidgets.forEach((widget) => {
    const digitalTime = widget.querySelector(".digital-time");
    digitalTime.textContent = displayTime;
    digitalTime.dateTime = now.toISOString();
    widget.querySelector(".clock-hand--hour").style.transform = `translateX(-50%) rotate(${hours * 30}deg)`;
    widget.querySelector(".clock-hand--minute").style.transform = `translateX(-50%) rotate(${minutes * 6}deg)`;
    widget.querySelector(".clock-hand--second").style.transform = `translateX(-50%) rotate(${seconds * 6}deg)`;
  });
}

updateClocks();
window.setInterval(updateClocks, 1000);
