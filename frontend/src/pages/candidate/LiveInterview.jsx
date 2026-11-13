import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  Camera,
  CameraOff,
  Mic,
  Mic2,
  Clock,
  BrainCircuit,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";

import {
  submitAnswer,
  getInterview,
  speakQuestion,
  getDeepgramToken,
} from "../../services/api";

const DEEPGRAM_MODEL = "nova-3";
const DEEPGRAM_LANGUAGE = "en-IN";
const SILENCE_DURATION_MS = 4000;

export default function LiveInterview() {
  const location = useLocation();
  const navigate = useNavigate();

  const sessionId =
    location.state?.sessionId ||
    sessionStorage.getItem("interviewSessionId");

  const candidateName =
    location.state?.candidateName ||
    sessionStorage.getItem("candidateName") ||
    "Candidate";

  // =========================================
  // REFERENCES
  // =========================================

  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);

  // Deepgram streaming references
  const deepgramSocketRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const deepgramConnectingRef = useRef(false);
  const deepgramReadyRef = useRef(false);
  const finalizingRef = useRef(false);
  const finalTranscriptPartsRef = useRef([]);
  const interimTranscriptRef = useRef("");
  const finalizeTimeoutRef = useRef(null);

  const restartTimerRef = useRef(null);
  const vadIntervalRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);

  const speechStartedRef = useRef(false);
  const silenceStartedAtRef = useRef(null);
  const autoSubmitLockRef = useRef(false);

  const listeningWantedRef = useRef(false);
  const transcriptRef = useRef("");

  const micEnabledRef = useRef(false);
  const submittingRef = useRef(false);
  const completedRef = useRef(false);

  // Fullscreen proctoring refs
  const interviewStartedRef = useRef(false);
  const pausedRef = useRef(false);
  const violationCountRef = useRef(0);
  const terminationRef = useRef(false);
  const countdownTimerRef = useRef(null);

  // =========================================
  // CAMERA AND MICROPHONE STATES
  // =========================================

  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [micEnabled, setMicEnabled] = useState(false);
  const [permissionError, setPermissionError] = useState("");

  // =========================================
  // INTERVIEW STATES
  // =========================================

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const [stage, setStage] = useState("INTRO");
  const [questionNumber, setQuestionNumber] = useState(1);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);

  const [secondsElapsed, setSecondsElapsed] = useState(0);

  // =========================================
  // FULLSCREEN PROCTORING STATES
  // =========================================

  const [proctoringReady, setProctoringReady] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [fullscreenWarning, setFullscreenWarning] = useState(false);
  const [violationCount, setViolationCount] = useState(0);
  const [countdown, setCountdown] = useState(8);
  const [terminated, setTerminated] = useState(false);
  const [proctoringMessage, setProctoringMessage] = useState("");

  // =========================================
  // AI VOICE STATES
  // =========================================

  const [voiceStatus, setVoiceStatus] = useState("idle");

  // idle | generating | speaking | ready | error

  // =========================================
  // DEEPGRAM SPEECH STATES
  // =========================================

  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [speechError, setSpeechError] = useState("");
  const [silenceCountdown, setSilenceCountdown] = useState(4);

  // =========================================
  // KEEP REFS SYNCHRONIZED
  // =========================================

  useEffect(() => {
    micEnabledRef.current = micEnabled;
  }, [micEnabled]);

  useEffect(() => {
    submittingRef.current = submitting;
  }, [submitting]);

  useEffect(() => {
    completedRef.current = completed;
  }, [completed]);

  useEffect(() => {
    pausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    violationCountRef.current = violationCount;
  }, [violationCount]);

  // =========================================
  // STOP DEEPGRAM AND AUDIO CAPTURE
  // =========================================

  const stopListening = () => {
    listeningWantedRef.current = false;
    deepgramReadyRef.current = false;
    deepgramConnectingRef.current = false;
    finalizingRef.current = false;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    if (finalizeTimeoutRef.current) {
      clearTimeout(finalizeTimeoutRef.current);
      finalizeTimeoutRef.current = null;
    }

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    speechStartedRef.current = false;
    silenceStartedAtRef.current = null;
    autoSubmitLockRef.current = false;

    setSilenceCountdown(4);
    setIsListening(false);

    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;

    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.ondataavailable = null;
        recorder.stop();
      } catch (err) {
        console.warn("MediaRecorder stop:", err);
      }
    }

    const socket = deepgramSocketRef.current;
    deepgramSocketRef.current = null;

    if (socket) {
      try {
        if (socket.readyState === WebSocket.OPEN) {
          socket.close(1000, "Interview listening stopped");
        } else if (socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      } catch (err) {
        console.warn("Deepgram socket close:", err);
      }
    }
  };

  // =========================================
  // STOP ALL INTERVIEW ACTIVITY
  // =========================================

  const stopInterviewActivity = () => {
    stopListening();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
  };

  // =========================================
  // TERMINATE INTERVIEW
  // =========================================

  const terminateInterview = async (reason) => {
    if (terminationRef.current) return;

    terminationRef.current = true;
    completedRef.current = true;
    listeningWantedRef.current = false;

    stopInterviewActivity();

    if (countdownTimerRef.current) {
      clearTimeout(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }

    setFullscreenWarning(false);
    setIsPaused(false);
    setTerminated(true);
    setProctoringMessage(reason);

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setCameraEnabled(false);
    setMicEnabled(false);

    try {
      const baseUrl =
        import.meta.env.VITE_API_BASE_URL ||
        "http://127.0.0.1:8000";

      await fetch(
        `${baseUrl}/interviews/${sessionId}/terminate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            reason,
            violation_count: violationCountRef.current,
          }),
        }
      );
    } catch (err) {
      console.error("Interview termination request failed:", err);
    }
  };

  // =========================================
  // FULLSCREEN WARNING COUNTDOWN
  // =========================================

  const startViolationCountdown = () => {
    if (countdownTimerRef.current) {
      clearTimeout(countdownTimerRef.current);
    }

    setCountdown(8);

    let remaining = 8;

    const tick = () => {
      remaining -= 1;
      setCountdown(remaining);

      if (remaining <= 0) {
        countdownTimerRef.current = null;

        terminateInterview(
          "Interview terminated because fullscreen mode was not restored."
        );

        return;
      }

      countdownTimerRef.current = setTimeout(tick, 1000);
    };

    countdownTimerRef.current = setTimeout(tick, 1000);
  };

  // =========================================
  // ENTER FULLSCREEN
  // =========================================

  const enterFullscreen = async () => {
    try {
      const element = document.documentElement;

      if (!document.fullscreenElement) {
        await element.requestFullscreen();
      }

      interviewStartedRef.current = true;
      pausedRef.current = false;

      setIsPaused(false);
      setFullscreenWarning(false);
      setProctoringReady(true);

      if (countdownTimerRef.current) {
        clearTimeout(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
    } catch (err) {
      console.error("Fullscreen request failed:", err);

      setError(
        "Unable to enter fullscreen mode. Please allow fullscreen access and try again."
      );
    }
  };

  // =========================================
  // HANDLE FULLSCREEN CHANGES
  // =========================================

  useEffect(() => {
    const handleFullscreenChange = () => {
      if (!interviewStartedRef.current || completedRef.current) {
        return;
      }

      if (!document.fullscreenElement) {
        if (pausedRef.current || terminationRef.current) return;

        const nextViolation = violationCountRef.current + 1;

        violationCountRef.current = nextViolation;
        setViolationCount(nextViolation);

        pausedRef.current = true;
        setIsPaused(true);
        setFullscreenWarning(true);

        stopInterviewActivity();

        if (nextViolation > 2) {
          terminateInterview(
            "Interview terminated because the fullscreen violation limit was exceeded."
          );
          return;
        }

        startViolationCountdown();
      }
    };

    document.addEventListener(
      "fullscreenchange",
      handleFullscreenChange
    );

    return () => {
      document.removeEventListener(
        "fullscreenchange",
        handleFullscreenChange
      );
    };
  }, []);

  // =========================================
  // RESTORE FULLSCREEN
  // =========================================

  const restoreFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      }

      if (countdownTimerRef.current) {
        clearTimeout(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }

      pausedRef.current = false;

      setIsPaused(false);
      setFullscreenWarning(false);
      setCountdown(8);
    } catch (err) {
      console.error("Unable to restore fullscreen:", err);

      setSpeechError(
        "Please use the fullscreen button to resume your interview."
      );
    }
  };

  // =========================================
  // CAMERA AND MICROPHONE INITIALIZATION
  // =========================================

  useEffect(() => {
    let mounted = true;

    const initializeMedia = async () => {
      try {
        const mediaStream =
          await navigator.mediaDevices.getUserMedia({
            video: {
              facingMode: "user",
              width: 1280,
              height: 720,
            },
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });

        if (!mounted) {
          mediaStream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = mediaStream;

        const videoTrack = mediaStream.getVideoTracks()[0];
        const audioTrack = mediaStream.getAudioTracks()[0];

        setCameraEnabled(Boolean(videoTrack?.enabled));
        setMicEnabled(Boolean(audioTrack?.enabled));

        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;

          try {
            await videoRef.current.play();
          } catch (playError) {
            console.warn("Camera preview autoplay:", playError);
          }
        }

        setPermissionError("");
      } catch (err) {
        console.error("Media initialization failed:", err);

        if (mounted) {
          setPermissionError(
            "Camera and microphone access is required. Please allow both permissions in your browser and reload the interview."
          );
        }
      }
    };

    initializeMedia();

    return () => {
      mounted = false;
    };
  }, []);

  // =========================================
  // CAMERA PREVIEW
  // =========================================

  useEffect(() => {
    const video = videoRef.current;

    if (!video || !streamRef.current) return;

    video.srcObject = streamRef.current;

    const playVideo = () => {
      video.play().catch((err) => {
        console.warn("Video preview could not autoplay:", err);
      });
    };

    if (video.readyState >= 2) {
      playVideo();
    } else {
      video.onloadedmetadata = playVideo;
    }

    return () => {
      video.onloadedmetadata = null;
    };
  }, [loading, cameraEnabled]);

  // =========================================
  // DEEPGRAM SUPPORT CHECK
  // =========================================

  useEffect(() => {
    const supported =
      Boolean(window.WebSocket) &&
      Boolean(window.MediaRecorder) &&
      Boolean(navigator.mediaDevices?.getUserMedia);

    setSpeechSupported(supported);

    if (!supported) {
      setSpeechError(
        "Your browser does not support live audio streaming. Please use the latest Chrome or Edge."
      );
    }
  }, []);

  // =========================================
  // DEEPGRAM TRANSCRIPT HANDLER
  // =========================================

  const handleDeepgramMessage = (event) => {
    let message;

    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }

    const transcript =
      message.channel?.alternatives?.[0]?.transcript?.trim() || "";

    if (!transcript) return;

    if (message.type === "Results") {
      if (message.is_final) {
        finalTranscriptPartsRef.current.push(transcript);

        transcriptRef.current =
          finalTranscriptPartsRef.current.join(" ").trim();

        interimTranscriptRef.current = "";

        setAnswer(transcriptRef.current);
        speechStartedRef.current = true;
      } else {
        interimTranscriptRef.current = transcript;

        const combined = [
          finalTranscriptPartsRef.current.join(" "),
          interimTranscriptRef.current,
        ]
          .filter(Boolean)
          .join(" ")
          .trim();

        setAnswer(combined);
      }
    }

    if (message.type === "Error") {
      console.error("Deepgram error:", message);

      setSpeechError(
        message.description ||
          message.message ||
          "Deepgram speech recognition encountered an error."
      );
    }
  };

  // =========================================
  // START DEEPGRAM STREAMING
  // =========================================

  const startListening = async () => {
    if (
      !speechSupported ||
      !micEnabledRef.current ||
      submittingRef.current ||
      completedRef.current ||
      pausedRef.current ||
      !proctoringReady ||
      terminationRef.current
    ) {
      return false;
    }

    if (listeningWantedRef.current || deepgramConnectingRef.current) {
      return false;
    }

    const stream = streamRef.current;

    if (!stream) {
      setSpeechError("Microphone stream is unavailable.");
      return false;
    }

    const audioTracks = stream.getAudioTracks();

    if (!audioTracks.length || !audioTracks[0].enabled) {
      setSpeechError(
        "Microphone is disabled. Please enable microphone access."
      );
      return false;
    }

    listeningWantedRef.current = true;
    deepgramConnectingRef.current = true;

    finalizingRef.current = false;
    finalTranscriptPartsRef.current = [];
    interimTranscriptRef.current = "";

    transcriptRef.current = "";
    setAnswer("");
    setSpeechError("");
    setIsListening(false);

    try {
      // Request a short-lived token from our FastAPI backend.
      const tokenResponse = await getDeepgramToken(sessionId);

      if (!listeningWantedRef.current) {
        deepgramConnectingRef.current = false;
        return false;
      }

      const accessToken = tokenResponse.access_token;

      if (!accessToken) {
        throw new Error("The backend did not return a Deepgram token.");
      }

      const params = new URLSearchParams({
        model: DEEPGRAM_MODEL,
        language: DEEPGRAM_LANGUAGE,
        smart_format: "true",
        interim_results: "true",
        punctuate: "true",
        endpointing: "300",
        utterance_end_ms: "1000",
        vad_events: "true",
      });

      const socketUrl =
        `wss://api.deepgram.com/v1/listen?${params.toString()}`;

      // Browser WebSocket authentication with a temporary JWT.
      const socket = new WebSocket(
        socketUrl,
        ["bearer", accessToken]
      );

      deepgramSocketRef.current = socket;

      socket.onopen = () => {
        deepgramConnectingRef.current = false;

        if (!listeningWantedRef.current) {
          socket.close();
          return;
        }

        try {
          const audioOnlyStream = new MediaStream(audioTracks);

          let mimeType = "";

          const supportedTypes = [
            "audio/webm;codecs=opus",
            "audio/webm",
            "audio/mp4",
          ];

          for (const type of supportedTypes) {
            if (MediaRecorder.isTypeSupported(type)) {
              mimeType = type;
              break;
            }
          }

          const recorder = mimeType
            ? new MediaRecorder(audioOnlyStream, { mimeType })
            : new MediaRecorder(audioOnlyStream);

          mediaRecorderRef.current = recorder;

          recorder.ondataavailable = (event) => {
            if (
              event.data &&
              event.data.size > 0 &&
              socket.readyState === WebSocket.OPEN &&
              !finalizingRef.current
            ) {
              socket.send(event.data);
            }
          };

          recorder.onerror = (event) => {
            console.error("MediaRecorder error:", event);
            setSpeechError("Microphone audio capture failed.");
          };

          recorder.start(250);

          deepgramReadyRef.current = true;
          setIsListening(true);
          setSpeechError("");

          console.log("Deepgram streaming connection established.");
        } catch (err) {
          console.error("Unable to start audio recorder:", err);

          setSpeechError(
            "Unable to capture microphone audio. Please check your browser permissions."
          );

          stopListening();
        }
      };

      socket.onmessage = handleDeepgramMessage;

      socket.onerror = (event) => {
        console.error("Deepgram WebSocket error:", event);

        deepgramConnectingRef.current = false;
        deepgramReadyRef.current = false;

        setSpeechError(
          "Speech recognition connection failed. Please try again."
        );

        setIsListening(false);
      };

      socket.onclose = (event) => {
        console.log(
          "Deepgram connection closed:",
          event.code,
          event.reason
        );

        deepgramConnectingRef.current = false;
        deepgramReadyRef.current = false;

        if (deepgramSocketRef.current === socket) {
          deepgramSocketRef.current = null;
        }

        if (listeningWantedRef.current && !finalizingRef.current) {
          setIsListening(false);
          setSpeechError(
            "Speech recognition disconnected. Please try speaking again."
          );
        }
      };

      return true;
    } catch (err) {
      console.error("Deepgram initialization failed:", err);

      deepgramConnectingRef.current = false;
      deepgramReadyRef.current = false;
      listeningWantedRef.current = false;

      setIsListening(false);

      setSpeechError(
        err.message ||
          "Unable to connect to Deepgram. Please try again."
      );

      return false;
    }
  };
    // =========================================
  // FORMAT INTERVIEW TIMER
  // =========================================

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(
      remainingSeconds
    ).padStart(2, "0")}`;
  };

  // =========================================
  // TERMINATED INTERVIEW
  // =========================================

  if (terminated) {
    return (
      <div className="min-h-screen bg-[#07091b] text-white flex items-center justify-center p-6">
        <div className="max-w-xl w-full bg-[#11182c] border border-red-500/30 rounded-2xl p-10 text-center">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-5" />

          <h1 className="text-3xl font-bold mb-3">
            Interview Terminated
          </h1>

          <p className="text-slate-300 mb-3">
            {proctoringMessage}
          </p>

          <p className="text-slate-400 mb-7">
            Your previously submitted answers have been retained.
          </p>

          <button
            onClick={() => navigate("/")}
            className="bg-purple-600 hover:bg-purple-700 px-7 py-3 rounded-xl font-semibold"
          >
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  // =========================================
  // COMPLETED INTERVIEW
  // =========================================

  if (completed) {
    return (
      <div className="min-h-screen bg-[#07091b] text-white flex items-center justify-center p-6">
        <div className="max-w-xl w-full bg-[#11182c] border border-white/10 rounded-2xl p-10 text-center">
          <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-5" />

          <h1 className="text-3xl font-bold mb-3">
            Interview Completed!
          </h1>

          <p className="text-slate-400 mb-7">
            Thank you, {candidateName}. Your interview responses
            have been submitted successfully.
          </p>

          <button
            onClick={() => navigate("/")}
            className="bg-purple-600 hover:bg-purple-700 px-7 py-3 rounded-xl font-semibold"
          >
            Back to Home
          </button>
        </div>
      </div>
    );
  }

  // =========================================
  // LOADING
  // =========================================

  if (loading) {
    return (
      <div className="min-h-screen bg-[#07091b] text-white flex items-center justify-center">
        <Loader2 className="animate-spin w-9 h-9 text-purple-400" />

        <span className="ml-3">
          Preparing your interview...
        </span>
      </div>
    );
  }

  // =========================================
  // MAIN INTERVIEW UI
  // =========================================

  return (
    <div className="min-h-screen bg-[#07091b] text-white">

      {/* FULLSCREEN START GATE */}
      {!proctoringReady && (
        <div className="fixed inset-0 z-[100] bg-[#07091b]/95 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="max-w-lg w-full bg-[#11182c] border border-white/10 rounded-2xl p-8 text-center shadow-2xl">
            <div className="w-16 h-16 rounded-2xl bg-purple-500/15 text-purple-300 flex items-center justify-center mx-auto mb-5">
              <AlertCircle size={34} />
            </div>

            <h2 className="text-2xl font-bold mb-3">
              Fullscreen Required
            </h2>

            <p className="text-slate-300 mb-4">
              Your interview will start in fullscreen mode. Leaving
              fullscreen will pause the interview and trigger a warning.
            </p>

            <p className="text-slate-400 text-sm mb-6">
              You have two warnings. If you do not return within 8 seconds,
              or exit fullscreen for a third time, the interview will be terminated.
            </p>

            {proctoringMessage && (
              <p className="text-yellow-300 text-sm mb-4">
                {proctoringMessage}
              </p>
            )}

            {permissionError && (
              <p className="text-red-300 text-sm mb-4">
                {permissionError}
              </p>
            )}

            <button
              onClick={enterFullscreen}
              disabled={
                loading ||
                Boolean(error) ||
                Boolean(permissionError) ||
                !cameraEnabled ||
                !micEnabled
              }
              className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 rounded-xl font-semibold"
            >
              Enable Fullscreen & Start Interview
            </button>
          </div>
        </div>
      )}

      {/* FULLSCREEN EXIT WARNING */}
      {fullscreenWarning && isPaused && (
        <div className="fixed inset-0 z-[110] bg-black/90 backdrop-blur-md flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-[#11182c] border border-yellow-500/40 rounded-2xl p-8 text-center shadow-2xl">
            <AlertCircle className="w-14 h-14 text-yellow-400 mx-auto mb-4" />

            <p className="text-yellow-300 text-sm font-semibold mb-2">
              WARNING {violationCount} OF 2
            </p>

            <h2 className="text-2xl font-bold mb-3">
              Return to Fullscreen
            </h2>

            <p className="text-slate-300 mb-5">
              Your interview is paused. Return to fullscreen immediately to continue.
            </p>

            <div className="text-5xl font-bold font-mono text-yellow-300 mb-5">
              00:{String(countdown).padStart(2, "0")}
            </div>

            <button
              onClick={restoreFullscreen}
              className="w-full bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-xl font-semibold"
            >
              Return to Fullscreen
            </button>

            <p className="text-slate-500 text-xs mt-4">
              If the countdown reaches zero, your interview will be terminated.
            </p>
          </div>
        </div>
      )}

      {/* HEADER */}
      <header className="border-b border-white/10 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-purple-600 p-2 rounded-xl">
            <BrainCircuit size={25} />
          </div>

          <h1 className="text-xl font-bold">
            Interview<span className="text-purple-400">AI</span>
          </h1>
        </div>

        <div className="flex items-center gap-2 text-red-400">
          <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
          LIVE INTERVIEW
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="max-w-7xl mx-auto p-6">
        {isPaused && (
          <div className="mb-5 rounded-xl border border-yellow-500/30 bg-yellow-500/10 p-4 text-yellow-200">
            Interview paused — return to fullscreen to continue.
          </div>
        )}

        {/* CANDIDATE DETAILS AND TIMER */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-7">
          <div>
            <p className="text-slate-400 text-sm">
              Candidate
            </p>

            <h2 className="text-xl font-semibold">
              {candidateName}
            </h2>
          </div>

          <div className="flex items-center gap-2 bg-[#11182c] border border-white/10 rounded-xl px-5 py-3">
            <Clock className="text-purple-400" size={20} />

            <span className="font-mono text-lg">
              {formatTime(secondsElapsed)}
            </span>
          </div>
        </div>

        {/* GENERAL ERROR */}
        {error && (
          <div className="mb-5 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex gap-2">
            <AlertCircle size={20} />
            {error}
          </div>
        )}

        {/* CAMERA PERMISSION ERROR */}
        {permissionError && (
          <div className="mb-5 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-200">
            {permissionError}
          </div>
        )}

        {/* MAIN GRID */}
        <div className="grid lg:grid-cols-2 gap-6">

          {/* CAMERA SECTION */}
          <section className="bg-[#11182c] border border-white/10 rounded-2xl p-5">
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">
                Candidate Camera
              </h3>
            </div>

            {/* VIDEO PREVIEW */}
            <div className="bg-black rounded-xl overflow-hidden aspect-video flex items-center justify-center">
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className={`w-full h-full object-cover ${
                  cameraEnabled ? "block" : "hidden"
                }`}
              />

              {!cameraEnabled && (
                <div className="text-center text-slate-500">
                  <CameraOff size={45} className="mx-auto mb-3" />
                  Camera unavailable
                </div>
              )}
            </div>

            <div className="flex justify-center gap-3 mt-5">
              <div className="flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-300">
                <Camera size={17} />
                Camera required
              </div>

              <div className="flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-2 text-sm text-green-300">
                <Mic size={17} />
                Microphone locked
              </div>
            </div>

            <p className="text-xs text-center text-slate-500 mt-4">
              Camera and microphone controls are locked during the interview.
              Camera preview is active; video is not recorded or stored.
            </p>
          </section>

          {/* QUESTION AND ANSWER SECTION */}
          <section className="bg-[#11182c] border border-white/10 rounded-2xl p-6">

            {/* QUESTION HEADER */}
            <div className="flex items-center justify-between mb-5">
              <span className="text-purple-400 text-sm font-semibold">
                INTERVIEW QUESTION
              </span>

              <span className="text-slate-400 text-sm">
                Question {questionNumber}
              </span>
            </div>

            {/* QUESTION DISPLAY */}
            <div className="bg-[#211b46] border border-purple-500/20 rounded-xl p-6 mb-6">
              <p className="text-xs text-purple-300 mb-3">
                {stage}
              </p>

              <h2 className="text-xl md:text-2xl font-semibold leading-relaxed">
                {question || "Waiting for the next question..."}
              </h2>
            </div>

            {/* VOICE-ONLY ANSWER STATUS */}
            <div className="rounded-xl border border-white/10 bg-[#07091b] p-6">
              <div className="flex items-center justify-between mb-4">
                <span className="text-sm font-semibold">
                  VOICE RESPONSE
                </span>

                {isListening ? (
                  <span className="flex items-center gap-2 text-red-400 text-sm">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                    Listening
                  </span>
                ) : submitting ? (
                  <span className="text-purple-300 text-sm">
                    Evaluating answer...
                  </span>
                ) : (
                  <span className="text-slate-400 text-sm">
                    Waiting
                  </span>
                )}
              </div>

              <div className="flex flex-col items-center text-center py-5">
                <div
                  className={`w-20 h-20 rounded-full flex items-center justify-center mb-4 ${
                    isListening
                      ? "bg-red-500/15 text-red-400"
                      : "bg-purple-500/15 text-purple-300"
                  }`}
                >
                  {submitting ? (
                    <Loader2 className="animate-spin" size={34} />
                  ) : (
                    <Mic2 size={34} />
                  )}
                </div>

                <p className="text-lg font-semibold mb-2">
                  {isPaused
                    ? "Interview paused"
                    : voiceStatus === "speaking"
                    ? "Please listen to the question"
                    : isListening
                    ? "Please speak your answer"
                    : submitting
                    ? "Processing your response"
                    : "Preparing your response"}
                </p>

                <p className="text-sm text-slate-400">
                  {isPaused
                    ? "Return to fullscreen to continue the interview."
                    : isListening
                    ? speechStartedRef.current
                      ? `Silence detected. Auto-submit in ${silenceCountdown} seconds.`
                      : "Start speaking when you are ready. The silence timer starts after your voice is detected."
                    : "Your answer is captured automatically. No typing or manual submission is required."}
                </p>
              </div>

              {speechError && (
                <div className="mt-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm flex gap-2">
                  <AlertCircle size={18} className="shrink-0" />
                  {speechError}
                </div>
              )}
            </div>
          </section>
        </div>

        {/* FOOTER */}
        <div className="mt-6 text-center text-xs text-slate-500">
          Your recognized answers are submitted to the AI Interview Engine.
          Audio recordings are not stored by this application.
        </div>
      </main>
    </div>
  );
}