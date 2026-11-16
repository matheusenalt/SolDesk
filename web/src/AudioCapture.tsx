import { useEffect, useRef, useState } from "react";
import { request } from "./workspace-api";
import { mediaStrings as s } from "./media-strings";

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  abort(): void;
  onresult:
    | ((event: {
        resultIndex: number;
        results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
      }) => void)
    | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

export function AudioCapture({
  file,
  onFile,
  live,
  onLive,
  onUseLive,
  onBusy,
}: {
  file: File | null;
  onFile: (value: File | null) => void;
  live: string;
  onLive: (value: string) => void;
  onUseLive: () => void;
  onBusy: (value: boolean) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [permission, setPermission] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const [liveAllowed, setLiveAllowed] = useState(false);
  const [consent, setConsent] = useState(false);
  const [liveRunning, setLiveRunning] = useState(false);
  const [provider, setProvider] = useState("");
  const [maxSeconds, setMaxSeconds] = useState(600);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const mounted = useRef(true);
  const liveRef = useRef(live);
  liveRef.current = live;
  const secure = window.isSecureContext;
  const supported =
    secure &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";
  const Speech =
    (window as SpeechWindow).SpeechRecognition ||
    (window as SpeechWindow).webkitSpeechRecognition;
  useEffect(() => {
    onBusy(recording || permission || liveRunning);
    return () => onBusy(false);
  }, [recording, permission, liveRunning, onBusy]);

  useEffect(() => {
    mounted.current = true;
    void request<{
      live_dictation_enabled: boolean;
      provider: string;
      max_seconds: number;
    }>("/media/settings")
      .then((value) => {
        if (mounted.current) {
          setLiveAllowed(value.live_dictation_enabled);
          setProvider(value.provider);
          setMaxSeconds(value.max_seconds);
        }
      })
      .catch(() => {});
    return () => {
      mounted.current = false;
      recognition.current?.abort();
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (!recording) return;
    const started = Date.now();
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - started) / 1000);
      setSeconds(elapsed);
      if (elapsed >= maxSeconds && recorder.current?.state === "recording")
        recorder.current.stop();
    }, 250);
    return () => clearInterval(timer);
  }, [recording, maxSeconds]);

  async function start() {
    setError("");
    setPermission(true);
    try {
      const input = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) {
        input.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = input;
      const mime = [
        "audio/webm;codecs=opus",
        "audio/ogg;codecs=opus",
        "audio/mp4",
      ].find((value) => MediaRecorder.isTypeSupported(value));
      const recording = new MediaRecorder(
        input,
        mime ? { mimeType: mime } : undefined,
      );
      recorder.current = recording;
      const chunks: BlobPart[] = [];
      recording.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recording.onstop = () => {
        input.getTracks().forEach((track) => track.stop());
        if (!mounted.current) return;
        const type = recording.mimeType || "audio/webm";
        const extension = type.includes("mp4")
          ? "m4a"
          : type.includes("ogg")
            ? "ogg"
            : "webm";
        onFile(new File(chunks, `gravacao.${extension}`, { type }));
        setRecording(false);
      };
      recording.onerror = () => {
        setError(s.microphoneError);
        input.getTracks().forEach((track) => track.stop());
        setRecording(false);
      };
      setSeconds(0);
      recording.start(1000);
      setRecording(true);
    } catch {
      setError(s.microphoneError);
    } finally {
      setPermission(false);
    }
  }
  function startLive() {
    if (!Speech || !consent || !liveAllowed || recording) return;
    const value = new Speech();
    recognition.current = value;
    value.lang = "pt-BR";
    value.continuous = true;
    value.interimResults = false;
    value.onresult = (event) => {
      let addition = "";
      for (let index = event.resultIndex; index < event.results.length; index++)
        if (event.results[index].isFinal)
          addition += event.results[index][0].transcript + " ";
      const updated = (liveRef.current + " " + addition).trim();
      liveRef.current = updated;
      onLive(updated);
    };
    value.onerror = () => {
      setError(s.liveError);
      setLiveRunning(false);
    };
    value.onend = () => setLiveRunning(false);
    try {
      value.start();
      setLiveRunning(true);
    } catch {
      setError(s.liveError);
    }
  }
  return (
    <fieldset className="audio-capture">
      <legend>{s.title}</legend>
      <p>{s.manual}</p>
      {provider === "mock" && <p>{s.mock}</p>}
      {!secure ? (
        <p role="note">{s.insecure}</p>
      ) : (
        !supported && <p>{s.unsupported}</p>
      )}
      {error && <p role="alert">! {error}</p>}
      {permission && <p role="status">{s.permission}</p>}
      {supported && (
        <>
          <button
            type="button"
            disabled={recording || permission || liveRunning}
            onClick={() => void start()}
          >
            {s.record}
          </button>
          <button
            type="button"
            disabled={!recording}
            onClick={() => recorder.current?.stop()}
          >
            {s.stop}
          </button>
          {recording && (
            <p role="status">
              {s.recording}: {seconds} {s.seconds}
            </p>
          )}
        </>
      )}
      <label>
        {s.file}
        <input
          aria-label={s.file}
          type="file"
          accept=".webm,.ogg,.opus,.mp4,.m4a,.aac,.wav,.mp3"
          disabled={recording || permission}
          onChange={(event) => onFile(event.target.files?.[0] || null)}
        />
      </label>
      {preview && (
        <>
          <audio aria-label={s.preview} controls src={preview} />
          <button type="button" onClick={() => onFile(null)}>
            {s.cancel}
          </button>
        </>
      )}
      {liveAllowed ? (
        secure && Speech ? (
          <>
            <label>
              <input
                type="checkbox"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
              />
              {s.livePrivacy}
            </label>
            <button
              type="button"
              disabled={!consent || recording || liveRunning}
              onClick={startLive}
            >
              {s.liveStart}
            </button>
            <button
              type="button"
              disabled={!liveRunning}
              onClick={() => recognition.current?.abort()}
            >
              {s.liveStop}
            </button>
          </>
        ) : (
          <p>{s.liveUnsupported}</p>
        )
      ) : (
        <p>{s.liveDisabled}</p>
      )}
      {live && (
        <>
          <label>
            {s.liveText}
            <textarea readOnly value={live} />
          </label>
          <button type="button" onClick={onUseLive}>
            {s.liveUse}
          </button>
        </>
      )}
    </fieldset>
  );
}
