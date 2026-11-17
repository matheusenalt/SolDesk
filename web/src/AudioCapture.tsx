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
  const [paused, setPaused] = useState(false);
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
  const captureLock = useRef(false);
  const elapsed = useRef(0);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const liveRef = useRef(live);
  liveRef.current = live;
  const secure = window.isSecureContext;
  const supported =
    secure &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined" &&
    typeof MediaRecorder.isTypeSupported === "function";
  const Speech =
    (window as SpeechWindow).SpeechRecognition ||
    (window as SpeechWindow).webkitSpeechRecognition;
  useEffect(() => {
    if (!recording && !permission && !file) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [recording, permission, file]);
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
      if (recorder.current && recorder.current.state !== "inactive")
        recorder.current.stop();
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
    if (!recording || paused) return;
    const started = performance.now();
    const previous = elapsed.current;
    const timer = setInterval(() => {
      const duration = previous + (performance.now() - started) / 1000;
      elapsed.current = duration;
      setSeconds(Math.floor(duration));
      if (duration >= maxSeconds && recorder.current?.state === "recording")
        recorder.current.stop();
    }, 250);
    return () => clearInterval(timer);
  }, [recording, paused, maxSeconds]);

  async function start() {
    if (captureLock.current) return;
    captureLock.current = true;
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
      if (!mime) throw new DOMException("", "NotSupportedError");
      const recording = new MediaRecorder(input, { mimeType: mime });
      recorder.current = recording;
      const chunks: BlobPart[] = [];
      let failed = false;
      input.getAudioTracks().forEach((track) => {
        track.onended = () => {
          if (!mounted.current || recording.state === "inactive") return;
          setError(s.interrupted);
          recording.stop();
        };
      });
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
        const result = new File(chunks, `gravacao.${extension}`, { type });
        if (!failed && result.size) onFile(result);
        else if (!failed) setError(s.emptyAudio);
        setRecording(false);
        setPaused(false);
        captureLock.current = false;
      };
      recording.onerror = () => {
        failed = true;
        setError(s.microphoneError);
        if (recording.state !== "inactive") recording.stop();
        input.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setPaused(false);
        captureLock.current = false;
      };
      onFile(null);
      elapsed.current = 0;
      setSeconds(0);
      setPaused(false);
      recording.start(1000);
      setRecording(true);
    } catch (err) {
      stream.current?.getTracks().forEach((track) => track.stop());
      captureLock.current = false;
      const name = err instanceof DOMException ? err.name : "";
      setError(
        name === "NotFoundError"
          ? s.noMicrophone
          : name === "NotSupportedError"
            ? s.badFormat
            : s.microphoneError,
      );
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
            onClick={() => {
              const active = recorder.current;
              if (active && active.state !== "inactive") active.stop();
            }}
          >
            {s.stop}
          </button>
          {typeof MediaRecorder.prototype.pause === "function" &&
            typeof MediaRecorder.prototype.resume === "function" && (
              <button
                type="button"
                disabled={!recording}
                onClick={() => {
                  const active = recorder.current;
                  if (!active || active.state === "inactive") return;
                  try {
                    if (active.state === "paused") active.resume();
                    else active.pause();
                    setPaused(active.state === "paused");
                  } catch {
                    setError(s.interrupted);
                  }
                }}
              >
                {paused ? s.resume : s.pause}
              </button>
            )}
          {recording && (
            <p role="status">
              {paused ? s.paused : s.recording}: {seconds} {s.seconds}
            </p>
          )}
        </>
      )}
      <label>
        {s.file}
        <input
          aria-label={s.file}
          ref={fileInput}
          type="file"
          accept=".webm,.ogg,.opus,.mp4,.m4a,.aac,.wav,.mp3"
          disabled={recording || permission || liveRunning}
          onChange={(event) => {
            const selected = event.target.files?.[0] || null;
            setError("");
            if (selected && !selected.size) {
              setError(s.emptyAudio);
              event.target.value = "";
              onFile(null);
            } else onFile(selected);
          }}
        />
      </label>
      {preview && (
        <>
          <audio aria-label={s.preview} controls src={preview} />
          <p role="note">{s.previewHint}</p>
          <button
            type="button"
            onClick={() => {
              if (fileInput.current) fileInput.current.value = "";
              onFile(null);
            }}
          >
            {s.cancel}
          </button>
        </>
      )}
      {(recording || permission || file) && <p role="note">{s.unsaved}</p>}
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
