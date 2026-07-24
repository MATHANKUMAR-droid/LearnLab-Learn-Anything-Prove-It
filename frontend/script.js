// ==========================================================================
// LearnLab — app logic
// A single-page app with 4 screens: auth -> learn -> test -> certificate
// ==========================================================================

const el = (id) => document.getElementById(id);

let AUTH_TOKEN = null;
let CURRENT_USER = null;   // { name, email }
let CURRENT_TOPIC = null;
let CURRENT_SESSION_ID = null;
let CURRENT_TEST_QUESTIONS = [];   // safe view (no answers) used for rendering
let SELECTED_ANSWERS = [];
let LAST_RESULTS = null;
let PENDING_OTP_PURPOSE = "signup";
let PENDING_OTP_EMAIL = "";

// ---------------------------------------------------------------------
// Connectivity banner
// ---------------------------------------------------------------------
function showConnBanner(text) {
  el("connBannerText").textContent = text ||
    "Can't reach the LearnLab server. Make sure \"python app.py\" is running, then refresh this page.";
  el("connBanner").hidden = false;
}
function hideConnBanner() {
  el("connBanner").hidden = true;
}

async function checkBackendHealth() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) hideConnBanner();
    else showConnBanner();
  } catch (err) {
    showConnBanner();
  }
}
checkBackendHealth();

// ---------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------
async function api(path, { method = "GET", body = null, auth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && AUTH_TOKEN) headers["Authorization"] = `Bearer ${AUTH_TOKEN}`;

  let res;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });
  } catch (networkErr) {
    showConnBanner();
    throw new Error("Can't reach the server. Make sure the Flask backend (python app.py) is running, then try again.");
  }

  hideConnBanner();
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

// ---------------------------------------------------------------------
// Screen / stepper navigation
// ---------------------------------------------------------------------
const SCREENS = ["auth", "learn", "test", "certificate"];

function goToScreen(name) {
  SCREENS.forEach(s => { el(`screen-${s}`).hidden = (s !== name); });
  const steps = document.querySelectorAll(".step");
  const idx = SCREENS.indexOf(name);
  steps.forEach((step, i) => {
    step.classList.remove("active", "done");
    if (i < idx) step.classList.add("done");
    else if (i === idx) step.classList.add("active");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------------------------------------------------------------------
// AUTH: tab switching
// ---------------------------------------------------------------------
document.querySelectorAll(".auth-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const form = tab.dataset.form;
    el("signupForm").hidden = form !== "signup";
    el("loginForm").hidden = form !== "login";
    el("otpForm").hidden = true;
  });
});

// ---------------------------------------------------------------------
// AUTH: sign up
// ---------------------------------------------------------------------
el("signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  el("signupError").textContent = "";
  const name = el("signupName").value.trim();
  const email = el("signupEmail").value.trim();
  const password = el("signupPassword").value;

  try {
    const data = await api("/api/auth/signup", { method: "POST", body: { name, email, password } });
    PENDING_OTP_PURPOSE = "signup";
    PENDING_OTP_EMAIL = email;
    showOtpForm(data);
  } catch (err) {
    el("signupError").textContent = err.message;
  }
});

// ---------------------------------------------------------------------
// AUTH: log in
// ---------------------------------------------------------------------
el("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  el("loginError").textContent = "";
  const email = el("loginEmail").value.trim();
  const password = el("loginPassword").value;

  try {
    const data = await api("/api/auth/login", { method: "POST", body: { email, password } });
    PENDING_OTP_PURPOSE = "login";
    PENDING_OTP_EMAIL = email;
    showOtpForm(data);
  } catch (err) {
    el("loginError").textContent = err.message;
  }
});

function showOtpForm(data) {
  el("signupForm").hidden = true;
  el("loginForm").hidden = true;
  el("otpForm").hidden = false;
  el("otpEmailLabel").textContent = PENDING_OTP_EMAIL;
  el("otpError").textContent = "";

  const banner = el("otpBanner");
  if (data.dev_mode) {
    banner.innerHTML = `<strong>Dev mode (no email server configured):</strong> your code is <strong style="font-family:'JetBrains Mono',monospace;">${data.otp_code}</strong>. It's shown here only because SMTP isn't set up.`;
    banner.hidden = false;
  } else {
    banner.innerHTML = `A 6-digit verification code was sent to your email. It expires in 10 minutes.`;
    banner.hidden = false;
  }

  const boxes = document.querySelectorAll(".otp-box");
  boxes.forEach(b => b.value = "");
  boxes[0].focus();
}

// OTP box auto-advance
document.querySelectorAll(".otp-box").forEach((box, i, all) => {
  box.addEventListener("input", () => {
    box.value = box.value.replace(/\D/g, "");
    if (box.value && i < all.length - 1) all[i + 1].focus();
  });
  box.addEventListener("keydown", (e) => {
    if (e.key === "Backspace" && !box.value && i > 0) all[i - 1].focus();
  });
});

el("otpForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  el("otpError").textContent = "";
  const code = Array.from(document.querySelectorAll(".otp-box")).map(b => b.value).join("");
  if (code.length !== 6) {
    el("otpError").textContent = "Please enter all 6 digits.";
    return;
  }
  try {
    const data = await api("/api/auth/verify-otp", {
      method: "POST",
      body: { email: PENDING_OTP_EMAIL, otp: code, purpose: PENDING_OTP_PURPOSE },
    });
    AUTH_TOKEN = data.token;
    CURRENT_USER = data.user;
    onLoggedIn();
  } catch (err) {
    el("otpError").textContent = err.message;
  }
});

el("resendOtpBtn").addEventListener("click", async () => {
  try {
    const data = await api("/api/auth/resend-otp", {
      method: "POST",
      body: { email: PENDING_OTP_EMAIL, purpose: PENDING_OTP_PURPOSE },
    });
    showOtpForm(data);
  } catch (err) {
    el("otpError").textContent = err.message;
  }
});

function onLoggedIn() {
  el("journeyUser").hidden = false;
  el("journeyUserName").textContent = CURRENT_USER.name;
  goToScreen("learn");
}

el("logoutBtn").addEventListener("click", () => {
  AUTH_TOKEN = null;
  CURRENT_USER = null;
  el("journeyUser").hidden = true;
  goToScreen("auth");
});

// ---------------------------------------------------------------------
// LEARN: generate lesson
// ---------------------------------------------------------------------
el("generateLessonBtn").addEventListener("click", async () => {
  const topic = el("topicInput").value.trim();
  el("topicError").textContent = "";
  if (!topic) {
    el("topicError").textContent = "Please describe a topic first.";
    return;
  }

  CURRENT_TOPIC = topic;
  el("topicCard").hidden = true;
  el("lessonContent").hidden = true;
  el("lessonLoading").hidden = false;
  el("loadingTopic").textContent = topic;

  try {
    const lesson = await api("/api/learn/generate", { method: "POST", auth: true, body: { topic } });
    CURRENT_SESSION_ID = lesson.session_id;
    renderLesson(lesson);
  } catch (err) {
    el("topicCard").hidden = false;
    el("topicError").textContent = err.message;
  } finally {
    el("lessonLoading").hidden = true;
  }
});

function renderLesson(lesson) {
  el("lessonTitle").textContent = lesson.title;
  el("lessonSummary").textContent = lesson.summary;
  el("templateNotice").hidden = lesson.source !== "template";

  // Video
  const q = encodeURIComponent(lesson.video_search_query || lesson.topic);
  el("lessonVideo").innerHTML = `
    <div class="video-card">
      <span class="video-icon">🎬</span>
      <div class="video-text">
        <strong>Watch a tutorial on this topic</strong>
        <span>${escapeHtml(lesson.video_search_query || lesson.topic)}</span>
      </div>
      <a class="video-link" href="https://www.youtube.com/results?search_query=${q}" target="_blank" rel="noopener">Find videos ↗</a>
    </div>`;

  // Key concepts
  el("lessonConcepts").innerHTML = (lesson.key_concepts || [])
    .map(c => `<span class="concept-chip">${escapeHtml(c)}</span>`).join("");

  // Sections
  el("lessonSections").innerHTML = (lesson.sections || [])
    .map(s => `<div class="lesson-section"><h4>${escapeHtml(s.heading)}</h4><p>${escapeHtml(s.content)}</p></div>`)
    .join("");

  // Example cases
  el("lessonExamples").innerHTML = (lesson.example_cases || []).map(ex => `
    <div class="example-card">
      <div class="ex-row"><span class="ex-label">Input</span>${escapeHtml(ex.input)}</div>
      <div class="ex-row"><span class="ex-label">Output</span>${escapeHtml(ex.output)}</div>
      <div class="ex-row"><span class="ex-label">Why</span>${escapeHtml(ex.explanation)}</div>
    </div>`).join("");

  // Mock questions (interactive, informal)
  el("mockQuestions").innerHTML = (lesson.mock_questions || []).map((q, qi) => `
    <div class="mock-q" data-qi="${qi}">
      <div class="mock-q-text">${qi + 1}. ${escapeHtml(q.question)}</div>
      ${q.options.map((opt, oi) => `<button class="mock-opt" data-oi="${oi}" data-correct="${oi === q.answer_index}">${escapeHtml(opt)}</button>`).join("")}
      <div class="mock-explain" hidden>${escapeHtml(q.explanation || "")}</div>
    </div>`).join("");

  el("mockQuestions").querySelectorAll(".mock-q").forEach(qEl => {
    qEl.querySelectorAll(".mock-opt").forEach(btn => {
      btn.addEventListener("click", () => {
        const opts = qEl.querySelectorAll(".mock-opt");
        const isCorrect = btn.dataset.correct === "true";
        opts.forEach(o => o.disabled = true);
        btn.classList.add(isCorrect ? "correct" : "wrong");
        if (!isCorrect) opts.forEach(o => { if (o.dataset.correct === "true") o.classList.add("correct"); });
        qEl.querySelector(".mock-explain").hidden = false;
      });
    });
  });

  el("lessonContent").hidden = false;
}

el("goToTestBtn").addEventListener("click", () => {
  goToScreen("test");
  startTest();
});

// ---------------------------------------------------------------------
// TEST: generate + take + submit
// ---------------------------------------------------------------------
async function startTest() {
  el("testLoading").hidden = false;
  el("testWrap").hidden = true;
  el("testResults").hidden = true;

  try {
    const data = await api("/api/test/generate", {
      method: "POST", auth: true,
      body: { topic: CURRENT_TOPIC, session_id: CURRENT_SESSION_ID },
    });
    CURRENT_TEST_QUESTIONS = data.questions;
    SELECTED_ANSWERS = new Array(CURRENT_TEST_QUESTIONS.length).fill(null);
    renderTestQuestions();
  } catch (err) {
    el("testLoading").innerHTML = `<p style="color:var(--red)">${err.message}</p>`;
  }
}

function renderTestQuestions() {
  el("testLoading").hidden = true;
  el("testWrap").hidden = false;

  el("testQuestions").innerHTML = CURRENT_TEST_QUESTIONS.map((q, qi) => `
    <div class="test-q-card" data-qi="${qi}">
      <div class="test-q-num">QUESTION ${qi + 1} OF ${CURRENT_TEST_QUESTIONS.length}</div>
      <div class="test-q-text">${escapeHtml(q.question)}</div>
      ${q.options.map((opt, oi) => `<button class="test-opt" data-oi="${oi}">${escapeHtml(opt)}</button>`).join("")}
    </div>`).join("");

  el("testQuestions").querySelectorAll(".test-q-card").forEach(card => {
    const qi = parseInt(card.dataset.qi, 10);
    card.querySelectorAll(".test-opt").forEach(btn => {
      btn.addEventListener("click", () => {
        card.querySelectorAll(".test-opt").forEach(o => o.classList.remove("selected"));
        btn.classList.add("selected");
        SELECTED_ANSWERS[qi] = parseInt(btn.dataset.oi, 10);
        updateTestProgress();
      });
    });
  });

  updateTestProgress();
}

function updateTestProgress() {
  const answered = SELECTED_ANSWERS.filter(a => a !== null).length;
  const total = CURRENT_TEST_QUESTIONS.length;
  el("testProgressFill").style.width = `${(answered / total) * 100}%`;
  el("testProgressLabel").textContent = `${answered} of ${total} answered`;
}

el("submitTestBtn").addEventListener("click", async () => {
  const unanswered = SELECTED_ANSWERS.filter(a => a === null).length;
  if (unanswered > 0) {
    const proceed = confirm(`You have ${unanswered} unanswered question(s). Submit anyway?`);
    if (!proceed) return;
  }
  el("submitTestBtn").disabled = true;
  el("submitTestBtn").textContent = "Grading…";

  try {
    const data = await api("/api/test/submit", {
      method: "POST", auth: true,
      body: { session_id: CURRENT_SESSION_ID, topic: CURRENT_TOPIC, answers: SELECTED_ANSWERS },
    });
    LAST_RESULTS = data;
    renderResults(data);
  } catch (err) {
    alert(err.message);
  } finally {
    el("submitTestBtn").disabled = false;
    el("submitTestBtn").textContent = "Submit test";
  }
});

function renderResults(data) {
  el("testWrap").hidden = true;
  el("testResults").hidden = false;

  el("resultPercentage").textContent = data.percentage;
  drawScoreRing(data.percentage, data.passed);

  if (data.passed) {
    el("resultHeadline").textContent = "You passed! 🎉";
    el("resultDetail").textContent =
      `You scored ${data.score} out of ${data.total} (${data.percentage}%) on "${CURRENT_TOPIC}" — that clears the ${data.pass_threshold}% threshold for a certificate.`;
    el("claimCertBtn").hidden = false;
  } else {
    el("resultHeadline").textContent = "Not quite there yet";
    el("resultDetail").textContent =
      `You scored ${data.score} out of ${data.total} (${data.percentage}%) on "${CURRENT_TOPIC}". You need ${data.pass_threshold}% to earn a certificate — review the material and try again.`;
    el("claimCertBtn").hidden = true;
  }

  el("answerReview").hidden = true;
  el("answerReview").innerHTML = data.results.map((r, i) => `
    <div class="review-item ${r.is_correct ? "correct" : "incorrect"}">
      <div class="review-q">${i + 1}. ${escapeHtml(r.question)}</div>
      <div class="review-answer your-answer ${r.is_correct ? "right" : "wrong"}">
        Your answer: ${r.selected_index !== null ? escapeHtml(r.options[r.selected_index]) : "— not answered —"}
      </div>
      ${!r.is_correct ? `<div class="review-answer" style="color:var(--green)">Correct answer: ${escapeHtml(r.options[r.correct_index])}</div>` : ""}
      <div class="review-explain">${escapeHtml(r.explanation || "")}</div>
    </div>`).join("");
}

function drawScoreRing(percentage, passed) {
  const canvas = el("scoreCanvas");
  const ctx = canvas.getContext("2d");
  const cx = canvas.width / 2, cy = canvas.height / 2, r = 68;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = "#E8E1D3";
  ctx.lineWidth = 12;
  ctx.stroke();

  const color = passed ? "#2E9E6D" : "#D64545";
  const endAngle = -Math.PI / 2 + (Math.PI * 2 * (percentage / 100));
  ctx.beginPath();
  ctx.arc(cx, cy, r, -Math.PI / 2, endAngle);
  ctx.strokeStyle = color;
  ctx.lineWidth = 12;
  ctx.lineCap = "round";
  ctx.stroke();
}

el("reviewAnswersBtn").addEventListener("click", () => {
  const review = el("answerReview");
  review.hidden = !review.hidden;
  el("reviewAnswersBtn").textContent = review.hidden ? "Review answers" : "Hide review";
});

el("retryTopicBtn").addEventListener("click", () => {
  el("topicCard").hidden = false;
  el("lessonContent").hidden = true;
  el("topicInput").value = "";
  goToScreen("learn");
});

// ---------------------------------------------------------------------
// CERTIFICATE
// ---------------------------------------------------------------------
el("claimCertBtn").addEventListener("click", async () => {
  el("claimCertBtn").disabled = true;
  el("claimCertBtn").textContent = "Generating…";
  try {
    const data = await api("/api/certificate/generate", {
      method: "POST", auth: true,
      body: { topic: CURRENT_TOPIC, percentage: LAST_RESULTS.percentage },
    });
    renderCertificateScreen(data);
    goToScreen("certificate");
  } catch (err) {
    alert(err.message);
  } finally {
    el("claimCertBtn").disabled = false;
    el("claimCertBtn").textContent = "Claim my certificate";
  }
});

function renderCertificateScreen(data) {
  el("certUserName").textContent = CURRENT_USER.name;
  el("certTopic").textContent = CURRENT_TOPIC;
  el("certScore").textContent = LAST_RESULTS.percentage;
  el("certPreviewName").textContent = CURRENT_USER.name;
  el("certPreviewTopic").textContent = CURRENT_TOPIC;
  el("downloadCertBtn").href = data.download_url;
}

el("learnAnotherBtn").addEventListener("click", () => {
  el("topicCard").hidden = false;
  el("lessonContent").hidden = true;
  el("topicInput").value = "";
  CURRENT_TOPIC = null;
  CURRENT_SESSION_ID = null;
  goToScreen("learn");
});

// ---------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str).replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[m]));
}

// Start on the auth screen
goToScreen("auth");
