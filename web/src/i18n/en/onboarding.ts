/** UI strings: view "onboarding". */
import type { Dict } from "../types";

export const dict: Dict = {
  // wizard shell
  "onboarding.welcome": "Welcome to {app}",
  "onboarding.closeHint": "Close — you can reopen the wizard from the sidebar",
  "onboarding.step.credentials": "Telegram API credentials",
  "onboarding.step.login": "Log in to Telegram",
  "onboarding.step.groups": "Choose groups to track",
  "onboarding.step.ai": "AI provider (optional)",
  "onboarding.step.sync": "First sync",
  "onboarding.allSet": "Everything is set up — you can close this wizard.",
  "onboarding.startUsing": "Start using {app}",
  "onboarding.setupComplete": "Setup complete — your archive is building",
  "onboarding.continue": "Continue",
  "onboarding.skip": "Skip for now",
  "onboarding.checking": "Checking…",

  // credentials step
  "onboarding.creds.title": "Connect your Telegram account",
  "onboarding.creds.intro":
    "Telegram requires every third-party app to use its own API credentials — creating them takes about a minute:",
  "onboarding.creds.step1.open": "Open",
  "onboarding.creds.step1.tools": "API development tools",
  "onboarding.creds.step2": "Create an app (any title; the rest can stay default)",
  "onboarding.creds.step3.copy": "Copy",
  "onboarding.creds.step3.and": "and",
  "onboarding.creds.step3.paste": "and paste them below",
  "onboarding.creds.envNote.a": "Values are stored in your local",
  "onboarding.creds.envNote.b": "file. Prefer editing files? Everything is documented in",
  "onboarding.recheckEnv": "I edited .env manually — check again",

  // login step
  "onboarding.login.phone": "Phone number (international)",
  "onboarding.login.send": "Send login code",
  "onboarding.login.sending": "Sending code…",
  "onboarding.login.codeSent":
    "Telegram sent a login code to your app or SMS. Enter it below.",
  "onboarding.login.code": "Login code",
  "onboarding.login.verify": "Verify",
  "onboarding.login.verifying": "Verifying…",
  "onboarding.login.resend": "Resend",
  "onboarding.login.2faIntro":
    "Your account has two-step verification enabled. Enter your cloud password.",
  "onboarding.login.2faPassword": "Two-step verification password",
  "onboarding.login.loggedInAs": "Logged in as {user}",

  // groups step
  "onboarding.groups.intro":
    "Tracked groups are copied into your local archive — their full history is downloaded so you can search and browse it. You can change this anytime in “{manage}”.",
  "onboarding.groups.load": "Load my groups",
  "onboarding.groups.listing": "listing your groups…",
  "onboarding.groups.reload": "reload list",
  "onboarding.groups.track": "Track",
  "onboarding.groups.pickAtLeastOne": "Tick at least one group",
  "onboarding.groups.loadTimeout": "Timed out loading the group list",

  // ai step
  "onboarding.ai.optional": "optional",
  "onboarding.ai.intro":
    "Ask-AI answers questions about your archive using any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, Ollama, LM Studio, vLLM…). You can verify the connection before saving.",
  "onboarding.ai.recheck": "re-check",
  "onboarding.ai.privacyNote":
    "Only retrieved message excerpts are sent to the endpoint when you ask a question — the rest of your archive never leaves this machine.",

  // sync step
  "onboarding.sync.intro":
    "Downloading the history of your tracked groups now. Large groups can take a while — you can keep using the app, stop the sync, and resume anytime without losing progress.",
  "onboarding.sync.start": "Start first sync",
  "onboarding.sync.backfilling": "Backfilling your group…",
  "onboarding.sync.syncing": "Syncing…",
  "onboarding.sync.queuedBehind": "Queued behind {jobs}…",
  "onboarding.sync.queuedStarting": "Sync queued — starting…",
  "onboarding.sync.starting": "(starting…)",
  "onboarding.sync.stop": "Stop (progress is saved)",
  "onboarding.sync.finish": "Finish setup",

  // shared setup forms (wizard + settings)
  "onboarding.form.apiId": "API ID",
  "onboarding.form.apiHash": "API hash",
  "onboarding.form.show": "show",
  "onboarding.form.hide": "hide",
  "onboarding.form.saving": "Saving…",
  "onboarding.form.saveContinue": "Save & continue",
  "onboarding.form.preset": "Provider preset",
  "onboarding.form.presetOllama": "Ollama (local)",
  "onboarding.form.presetCustom": "Custom…",
  "onboarding.form.endpoint": "Endpoint (base URL)",
  "onboarding.form.apiKey": "API key",
  "onboarding.form.keyAny": "any non-empty value (e.g. ollama)",
  "onboarding.form.model": "Model",
  "onboarding.form.test": "Test connection",
  "onboarding.form.testing": "Testing…",
  "onboarding.form.testOk": "{model} replied — connection works",
  "onboarding.form.keyNote.a": "The key is stored in your local",
  "onboarding.form.keyNote.b":
    "file and is never shown again or sent back to the browser.",
};
