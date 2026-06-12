const usernameDisplay = document.querySelector("#profile-username");
const emailDisplay = document.querySelector("#profile-email");
const commentsList = document.querySelector("#account-comments-list");
const postsList = document.querySelector("#account-posts-list");
const signOutButton = document.querySelector("#sign-out");

function renderActivity(container, items, emptyMessage) {
  container.replaceChildren();
  if (items.length === 0) {
    const emptyState = document.createElement("p");
    emptyState.className = "activity-empty";
    emptyState.textContent = emptyMessage;
    container.append(emptyState);
    return;
  }
  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "activity-item";
    const title = document.createElement("h3");
    title.textContent = item.title || "Forum activity";
    const body = document.createElement("p");
    body.textContent = item.body || "";
    article.append(title, body);
    if (item.date) {
      const date = document.createElement("time");
      date.dateTime = item.date;
      date.textContent = new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      }).format(new Date(item.date));
      article.append(date);
    }
    container.append(article);
  });
}

async function loadAccount() {
  try {
    const [profileResponse, activityResponse] = await Promise.all([
      fetch("/api/me"),
      fetch("/api/activity"),
    ]);
    if (profileResponse.status === 401 || activityResponse.status === 401) {
      window.location.href = "login.html";
      return;
    }
    const profile = await profileResponse.json();
    const activity = await activityResponse.json();
    if (!profileResponse.ok) throw new Error(profile.error || "Unable to load profile.");
    if (!activityResponse.ok) throw new Error(activity.error || "Unable to load activity.");

    usernameDisplay.textContent = profile.user.username;
    emailDisplay.textContent = profile.user.email;
    document.querySelectorAll(".account-avatar").forEach((avatar) => {
      avatar.style.backgroundImage = `url("${profile.user.profileImageUrl}")`;
    });
    renderActivity(commentsList, activity.comments, "You haven't posted any comments yet.");
    renderActivity(postsList, activity.posts, "You haven't created any forum posts yet.");
  } catch (error) {
    renderActivity(commentsList, [], error.message);
    renderActivity(postsList, [], error.message);
  }
}

signOutButton.addEventListener("click", async () => {
  await fetch("/api/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  window.location.href = "login.html";
});

loadAccount();
