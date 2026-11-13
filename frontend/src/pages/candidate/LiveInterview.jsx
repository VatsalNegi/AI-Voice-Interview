
import { useCallback, useEffect, useRef, useState } from "react";
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
  startInterview,
  submitAnswer,
  getInterview,
  speakQuestion,
  getDeepgramToken,
} from "../../services/api";

const DEEPGRAM_MODEL = "nova-3";
const DEEPGRAM_LANGUAGE = "en-IN";
const SILENCE_DURATION_MS = 4000;
const SILENCE_THRESHOLD = 0.025;

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

  // --------------------------------------------------
  // REFS
  // --------------------------------------------------

  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);

  const deepgramSocketRef = useRef(null);
  const mediaRecorderRef = useRef(null);

  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const vadIntervalRef = useRef(null);

  const finalTranscriptPartsRef = useRef([]);
  const interimTranscriptRef = useRef("");
  const transcriptRef = useRef("");

  const listeningWantedRef = useRef(false);
  const deepgramReadyRef = useRef(false);
  const deepgramConnectingRef = useRef(false);

  const speechStartedRef = useRef(false);
  const silenceStartedAtRef = useRef(null);

  const submittingRef = useRef(false);
  const completedRef = useRef(false);
  const initializationRef = useRef(false);

  const micEnabledRef = useRef(false);
  const pausedRef = useRef(false);

  const interviewStartedRef = useRef(false);
  const terminationRef = useRef(false);
  const violationCountRef = useRef(0);

  const countdownTimerRef = useRef(null);
  const silenceSubmitLockRef = useRef(false);

  const questionRef = useRef("");
  const mountedRef = useRef(true);

  // --------------------------------------------------
  // STATES
  // --------------------------------------------------

  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [micEnabled, setMicEnabled] = useState(false);
  const [permissionError, setPermissionError] = useState("");

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const [stage, setStage] = useState("Introduction");
  const [questionNumber, setQuestionNumber] = useState(1);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [completed, setCompleted] = useState(false);
  const [terminated, setTerminated] = useState(false);

  const [secondsElapsed, setSecondsElapsed] = useState(0);

  const [proctoringReady, setProctoringReady] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [fullscreenWarning, setFullscreenWarning] = useState(false);
  const [violationCount, setViolationCount] = useState(0);
  const [countdown, setCountdown] = useState(8);
  const [proctoringMessage, setProctoringMessage] = useState("");

  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [speechError, setSpeechError] = useState("");
  const [silenceCountdown, setSilenceCountdown] = useState(4);

  // --------------------------------------------------
  // SYNCHRONIZE REFS
  // --------------------------------------------------

  useEffect(() => {
    questionRef.current = question;
  }, [question]);

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

  // --------------------------------------------------
  // HELPERS
  // --------------------------------------------------

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(
      remaining
    ).padStart(2, "0")}`;
  };

  const extractQuestion = (data) => {
    if (!data) return null;

    if (typeof data === "string") {
      return {
        question: data,
        sequence_number: 1,
        stage: "introduction",
      };
    }

    if (typeof data.current_question === "string") {
      return {
        question: data.current_question,
        sequence_number: 1,
        stage: data.current_stage,
      };
    }

    if (data.current_question?.question) {
      return data.current_question;
    }

    if (data.first_question?.question) {
      return data.first_question;
    }

    if (data.next_question?.question) {
      return data.next_question;
    }

    if (data.question?.question) {
      return data.question;
    }

    if (typeof data.question === "string") {
      return {
        question: data.question,
        sequence_number: data.sequence_number || 1,
        stage: data.current_stage || data.stage,
      };
    }

    return null;
  };

  const displayQuestion = (questionData) => {
    if (!questionData?.question) {
      throw new Error("The interview response did not contain a question.");
    }

    setQuestion(questionData.question);
    questionRef.current = questionData.question;

    setStage(
      questionData.stage_label ||
        questionData.stage ||
        "Interview"
    );

    setQuestionNumber(
      questionData.sequence_number || 1
    );

    setAnswer("");
    transcriptRef.current = "";
    finalTranscriptPartsRef.current = [];
    interimTranscriptRef.current = "";
    speechStartedRef.current = false;
    silenceStartedAtRef.current = null;
    silenceSubmitLockRef.current = false;
    setSilenceCountdown(4);
  };

  // --------------------------------------------------
  // STOP DEEPGRAM
  // --------------------------------------------------

  const stopListening = useCallback(() => {
    listeningWantedRef.current = false;
    deepgramReadyRef.current = false;
    deepgramConnectingRef.current = false;

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
      analyserRef.current = null;
    }

    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;

    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.ondataavailable = null;
        recorder.stop();
      } catch (err) {
        console.warn("Recorder stop error:", err);
      }
    }

    const socket = deepgramSocketRef.current;
    deepgramSocketRef.current = null;

    if (socket) {
      try {
        socket.close(1000, "Listening stopped");
      } catch (err) {
        console.warn("Socket close error:", err);
      }
    }

    setIsListening(false);
    setSilenceCountdown(4);

    speechStartedRef.current = false;
    silenceStartedAtRef.current = null;
  }, []);

  // --------------------------------------------------
  // STOP ALL ACTIVITY
  // --------------------------------------------------

  const stopInterviewActivity = useCallback(() => {
    stopListening();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
  }, [stopListening]);

  // --------------------------------------------------
  // TERMINATE INTERVIEW
  // --------------------------------------------------

  const terminateInterview = useCallback(
    async (reason) => {
      if (terminationRef.current) return;

      terminationRef.current = true;
      completedRef.current = true;

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
        console.error("Termination request failed:", err);
      }
    },
    [sessionId, stopInterviewActivity]
  );

  // --------------------------------------------------
  // FULLSCREEN COUNTDOWN
  // --------------------------------------------------

  const startViolationCountdown = () => {
    if (countdownTimerRef.current) {
      clearTimeout(countdownTimerRef.current);
    }

    let remaining = 8;
    setCountdown(8);

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

  // --------------------------------------------------
  // ENTER FULLSCREEN
  // --------------------------------------------------

  const enterFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
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

      if (questionRef.current) {
        playQuestion(questionRef.current);
      }
    } catch (err) {
      console.error("Fullscreen error:", err);

      setError(
        "Unable to enter fullscreen mode. Please try again."
      );
    }
  };

  // --------------------------------------------------
  // RESTORE FULLSCREEN
  // --------------------------------------------------

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

      if (questionRef.current) {
        playQuestion(questionRef.current);
      }
    } catch (err) {
      console.error("Fullscreen restoration failed:", err);

      setProctoringMessage(
        "Please use the fullscreen button to resume."
      );
    }
  };

  // --------------------------------------------------
  // FULLSCREEN MONITORING
  // --------------------------------------------------

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
  }, [stopInterviewActivity, terminateInterview]);

  // --------------------------------------------------
  // CAMERA AND MICROPHONE
  // --------------------------------------------------

  useEffect(() => {
    let mounted = true;

    const initializeMedia = async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera and microphone access is not supported by this browser."
          );
        }

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
          } catch (err) {
            console.warn("Video autoplay:", err);
          }
        }

        setPermissionError("");
      } catch (err) {
        console.error("Media initialization failed:", err);

        if (mounted) {
          setPermissionError(
            err.message ||
              "Camera and microphone access is required. Please allow permissions and reload."
          );
        }
      }
    };

    initializeMedia();

    return () => {
      mounted = false;
    };
  }, []);

  // --------------------------------------------------
  // CAMERA PREVIEW
  // --------------------------------------------------

  useEffect(() => {
    if (!videoRef.current || !streamRef.current) return;

    videoRef.current.srcObject = streamRef.current;

    videoRef.current.play().catch((err) => {
      console.warn("Camera preview:", err);
    });
  }, [cameraEnabled, loading]);

  // --------------------------------------------------
  // DEEPGRAM SUPPORT
  // --------------------------------------------------

  useEffect(() => {
    const supported =
      Boolean(window.WebSocket) &&
      Boolean(window.MediaRecorder) &&
      Boolean(navigator.mediaDevices?.getUserMedia);

    setSpeechSupported(supported);

    if (!supported) {
      setSpeechError(
        "Please use the latest Chrome or Edge browser for voice recognition."
      );
    }
  }, []);

  // --------------------------------------------------
  // DEEPGRAM MESSAGE HANDLER
  // --------------------------------------------------

  const handleDeepgramMessage = (event) => {
    let message;

    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }

    if (message.type === "Error") {
      console.error("Deepgram error:", message);

      setSpeechError(
        message.description ||
          message.message ||
          "Speech recognition error."
      );

      return;
    }

    if (message.type !== "Results") return;

    const transcript =
      message.channel?.alternatives?.[0]?.transcript?.trim() || "";

    if (!transcript) return;

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
  };

  // --------------------------------------------------
  // START DEEPGRAM STREAMING
  // --------------------------------------------------

  const startListening = async () => {
    if (
      !speechSupported ||
      !micEnabledRef.current ||
      submittingRef.current ||
      completedRef.current ||
      pausedRef.current ||
      terminationRef.current
    ) {
      return false;
    }

    if (
      listeningWantedRef.current ||
      deepgramConnectingRef.current
    ) {
      return false;
    }

    const stream = streamRef.current;

    if (!stream) {
      setSpeechError("Microphone stream is unavailable.");
      return false;
    }

    const audioTracks = stream.getAudioTracks();

    if (!audioTracks.length || !audioTracks[0].enabled) {
      setSpeechError("Please enable microphone access.");
      return false;
    }

    listeningWantedRef.current = true;
    deepgramConnectingRef.current = true;

    finalTranscriptPartsRef.current = [];
    interimTranscriptRef.current = "";
    transcriptRef.current = "";

    speechStartedRef.current = false;
    silenceStartedAtRef.current = null;
    silenceSubmitLockRef.current = false;

    setAnswer("");
    setSpeechError("");
    setIsListening(false);
    setSilenceCountdown(4);

    try {
      const tokenResponse = await getDeepgramToken(sessionId);

      if (!listeningWantedRef.current) {
        deepgramConnectingRef.current = false;
        return false;
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

      const socket = new WebSocket(
        `wss://api.deepgram.com/v1/listen?${params.toString()}`,
        ["bearer", tokenResponse.access_token]
      );

      deepgramSocketRef.current = socket;

      await new Promise((resolve, reject) => {
        const connectionTimeout = setTimeout(() => {
          reject(new Error("Deepgram connection timed out."));
        }, 15000);

        socket.onopen = () => {
          clearTimeout(connectionTimeout);
          resolve();
        };

        socket.onerror = () => {
          clearTimeout(connectionTimeout);
          reject(new Error("Unable to connect to Deepgram."));
        };

        socket.onclose = (event) => {
          if (!deepgramReadyRef.current) {
            clearTimeout(connectionTimeout);

            reject(
              new Error(
                `Deepgram connection closed (${event.code}).`
              )
            );
          }
        };
      });

      if (!listeningWantedRef.current) {
        socket.close();
        return false;
      }

      const audioOnlyStream = new MediaStream(audioTracks);

      const supportedTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ];

      let mimeType = "";

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
          event.data?.size > 0 &&
          socket.readyState === WebSocket.OPEN
        ) {
          socket.send(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error("MediaRecorder error:", event);
        setSpeechError("Microphone audio capture failed.");
      };

      socket.onmessage = handleDeepgramMessage;

      socket.onclose = (event) => {
        deepgramReadyRef.current = false;
        deepgramConnectingRef.current = false;

        if (deepgramSocketRef.current === socket) {
          deepgramSocketRef.current = null;
        }

        if (
          listeningWantedRef.current &&
          !completedRef.current
        ) {
          setIsListening(false);

          console.warn(
            "Deepgram disconnected:",
            event.code,
            event.reason
          );

          setSpeechError(
            "Speech recognition disconnected. Please try again."
          );
        }
      };

      recorder.start(250);

      deepgramReadyRef.current = true;
      deepgramConnectingRef.current = false;

      setIsListening(true);
      setSpeechError("");

      // Start voice activity detection.
      const audioContext = new (
        window.AudioContext || window.webkitAudioContext
      )();

      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(
        audioOnlyStream
      );

      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;

      source.connect(analyser);
      analyserRef.current = analyser;

      const samples = new Uint8Array(analyser.fftSize);

      vadIntervalRef.current = setInterval(() => {
        if (
          !listeningWantedRef.current ||
          !deepgramReadyRef.current ||
          submittingRef.current ||
          pausedRef.current
        ) {
          return;
        }

        analyser.getByteTimeDomainData(samples);

        let sum = 0;

        for (let i = 0; i < samples.length; i++) {
          const normalized = (samples[i] - 128) / 128;
          sum += normalized * normalized;
        }

        const rms = Math.sqrt(sum / samples.length);

        if (rms > SILENCE_THRESHOLD) {
          speechStartedRef.current = true;
          silenceStartedAtRef.current = null;
          setSilenceCountdown(4);
        } else if (speechStartedRef.current) {
          if (!silenceStartedAtRef.current) {
            silenceStartedAtRef.current = Date.now();
          }

          const elapsed =
            Date.now() - silenceStartedAtRef.current;

          const remaining = Math.max(
            0,
            Math.ceil(
              (SILENCE_DURATION_MS - elapsed) / 1000
            )
          );

          setSilenceCountdown(remaining);

          if (
            elapsed >= SILENCE_DURATION_MS &&
            !silenceSubmitLockRef.current
          ) {
            silenceSubmitLockRef.current = true;
            handleSubmitAnswer();
          }
        }
      }, 200);

      console.log("Deepgram streaming started.");

      return true;
    } catch (err) {
      console.error("Deepgram initialization failed:", err);

      deepgramConnectingRef.current = false;
      deepgramReadyRef.current = false;
      listeningWantedRef.current = false;

      setIsListening(false);

      setSpeechError(
        err.message ||
          "Unable to connect to the speech recognition service."
      );

      const socket = deepgramSocketRef.current;

      if (socket) {
        try {
          socket.close();
        } catch {}
      }

      deepgramSocketRef.current = null;

      return false;
    }
  };

  // --------------------------------------------------
  // FINALIZE TRANSCRIPT
  // --------------------------------------------------

  const stopListeningAndGetTranscript = async () => {
    listeningWantedRef.current = false;
    deepgramReadyRef.current = false;

    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
      analyserRef.current = null;
    }

    const recorder = mediaRecorderRef.current;
    const socket = deepgramSocketRef.current;

    mediaRecorderRef.current = null;

    // Allow the final audio chunk to reach Deepgram.
    if (recorder && recorder.state !== "inactive") {
      await new Promise((resolve) => {
        recorder.onstop = resolve;

        try {
          recorder.stop();
        } catch {
          resolve();
        }
      });
    }

    // Give Deepgram time to process the last audio packets.
    await new Promise((resolve) => setTimeout(resolve, 1200));

    if (socket) {
      try {
        if (socket.readyState === WebSocket.OPEN) {
          socket.close(1000, "Finished speaking");
        }
      } catch {}
    }

    deepgramSocketRef.current = null;

    setIsListening(false);

    const finalText = [
      finalTranscriptPartsRef.current.join(" "),
      interimTranscriptRef.current,
    ]
      .filter(Boolean)
      .join(" ")
      .trim();

    transcriptRef.current = finalText;

    return finalText;
  };

  // --------------------------------------------------
  // PLAY AI QUESTION
  // --------------------------------------------------

  const playQuestion = async (text) => {
    if (
      !text ||
      completedRef.current ||
      pausedRef.current ||
      terminationRef.current
    ) {
      return;
    }

    stopListening();

    setVoiceStatus("generating");
    setSpeechError("");

    try {
      const audioBlob = await speakQuestion(text);

      if (completedRef.current || pausedRef.current) return;

      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }

      const audioUrl = URL.createObjectURL(audioBlob);
      audioUrlRef.current = audioUrl;

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      setVoiceStatus("speaking");

      audio.onended = () => {
        if (
          completedRef.current ||
          pausedRef.current ||
          terminationRef.current
        ) {
          return;
        }

        setVoiceStatus("ready");

        startListening();
      };

      audio.onerror = () => {
        console.error("Question audio playback failed.");

        setVoiceStatus("error");
        setSpeechError(
          "Unable to play the question audio. Please check your audio settings."
        );
      };

      await audio.play();
    } catch (err) {
      console.error("Question voice generation failed:", err);

      setVoiceStatus("error");

      setSpeechError(
        err.message ||
          "Unable to generate interviewer voice."
      );
    }
  };

  // --------------------------------------------------
  // SUBMIT ANSWER
  // --------------------------------------------------

  const handleSubmitAnswer = async () => {
    if (
      submittingRef.current ||
      completedRef.current ||
      pausedRef.current
    ) {
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);

    setVoiceStatus("generating");

    try {
      const transcript =
        await stopListeningAndGetTranscript();

      if (!transcript || transcript.trim().length < 2) {
        setSpeechError(
          "No clear answer was detected. Please try answering again."
        );

        submittingRef.current = false;
        setSubmitting(false);
        silenceSubmitLockRef.current = false;

        if (!pausedRef.current && !completedRef.current) {
          setTimeout(() => {
            if (questionRef.current) {
              playQuestion(questionRef.current);
            }
          }, 1000);
        }

        return;
      }

      setAnswer(transcript);

      console.log("Submitting candidate answer:", transcript);

      const response = await submitAnswer(
        sessionId,
        transcript
      );

      console.log("Answer submission response:", response);

      if (response.status === "completed" || response.completed) {
        completedRef.current = true;

        setCompleted(true);
        setSubmitting(false);
        submittingRef.current = false;

        stopInterviewActivity();

        if (streamRef.current) {
          streamRef.current
            .getTracks()
            .forEach((track) => track.stop());

          streamRef.current = null;
        }

        setCameraEnabled(false);
        setMicEnabled(false);

        return;
      }

      const nextQuestion = extractQuestion(response);

      if (nextQuestion) {
        displayQuestion(nextQuestion);
        setSubmitting(false);
        submittingRef.current = false;

        setTimeout(() => {
          if (!pausedRef.current && !completedRef.current) {
            playQuestion(nextQuestion.question);
          }
        }, 500);

        return;
      }

      // If the answer endpoint does not return the next question,
      // retrieve the updated session state from the backend.
      const updatedSession = await getInterview(sessionId);

      if (updatedSession.status === "completed") {
        completedRef.current = true;
        setCompleted(true);

        stopInterviewActivity();

        return;
      }

      const updatedQuestion = extractQuestion(updatedSession);

      if (updatedQuestion) {
        displayQuestion(updatedQuestion);

        setTimeout(() => {
          if (!pausedRef.current && !completedRef.current) {
            playQuestion(updatedQuestion.question);
          }
        }, 500);
      } else {
        throw new Error(
          "The answer was submitted, but the next question was not returned."
        );
      }
    } catch (err) {
      console.error("Answer submission failed:", err);

      setSpeechError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to submit your answer."
      );

      silenceSubmitLockRef.current = false;
    } finally {
      submittingRef.current = false;

      if (mountedRef.current) {
        setSubmitting(false);
      }
    }
  };

  // --------------------------------------------------
  // INITIALIZE / LOAD INTERVIEW
  // --------------------------------------------------

  useEffect(() => {
    let mounted = true;

    mountedRef.current = true;

    const initializeInterview = async () => {
      if (!sessionId) {
        setError(
          "Interview session ID is missing. Please restart your interview."
        );

        setLoading(false);
        return;
      }

      if (initializationRef.current) return;

      initializationRef.current = true;

      try {
        setLoading(true);
        setError("");

        console.log("Loading interview session:", sessionId);

        // First, check the existing session.
        let session = await getInterview(sessionId);

        console.log("Existing interview session:", session);

        if (!mounted) return;

        if (
          session.status === "completed" ||
          session.status === "terminated"
        ) {
          if (session.status === "completed") {
            setCompleted(true);
          } else {
            setTerminated(true);
            setProctoringMessage(
              session.termination_reason ||
                "This interview has been terminated."
            );
          }

          return;
        }

        if (session.preparation_status === "processing") {
          throw new Error(
            "Your interview is still being prepared. Please refresh after preparation is complete."
          );
        }

        if (session.preparation_status === "failed") {
          throw new Error(
            session.preparation_error ||
              "Interview preparation failed. Please contact the recruiter."
          );
        }

        let currentQuestion = extractQuestion(session);

        // Start only when the session has not started.
        if (
          session.status === "not_started" ||
          session.status === "pending"
        ) {
          console.log("Starting the interview...");

          const startResponse = await startInterview(sessionId);

          console.log("Start interview response:", startResponse);

          if (!mounted) return;

          if (
            startResponse.status === "completed" ||
            startResponse.completed
          ) {
            setCompleted(true);
            return;
          }

          currentQuestion = extractQuestion(startResponse);
        }

        // Some backends return the question in the session metadata
        // but not in current_question. Refresh once if needed.
        if (!currentQuestion) {
          session = await getInterview(sessionId);

          if (!mounted) return;

          currentQuestion = extractQuestion(session);
        }

        if (!currentQuestion) {
          throw new Error(
            "The interview session is ready, but no current question was found. Please check the backend start-interview response."
          );
        }

        displayQuestion(currentQuestion);

        console.log(
          "Interview initialized with question:",
          currentQuestion.question
        );
      } catch (err) {
        console.error("Interview initialization error:", err);

        if (mounted) {
          setError(
            err.response?.data?.detail ||
              err.message ||
              "Unable to prepare your interview."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    initializeInterview();

    return () => {
  mounted = false;
  mountedRef.current = false;

  // Reset initialization guard for React Strict Mode
  initializationRef.current = false;
};
  }, [sessionId]);

  // --------------------------------------------------
  // INTERVIEW TIMER
  // --------------------------------------------------

  useEffect(() => {
    if (!proctoringReady || completed || terminated || isPaused) {
      return;
    }

    const timer = setInterval(() => {
      setSecondsElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [proctoringReady, completed, terminated, isPaused]);

  // --------------------------------------------------
  // CLEANUP
  // --------------------------------------------------

  useEffect(() => {
    return () => {
      mountedRef.current = false;

      stopListening();

      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop());

        streamRef.current = null;
      }

      if (countdownTimerRef.current) {
        clearTimeout(countdownTimerRef.current);
      }
    };
  }, [stopListening]);

  // --------------------------------------------------
  // TERMINATED SCREEN
  // --------------------------------------------------

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

  // --------------------------------------------------
  // COMPLETED SCREEN
  // --------------------------------------------------

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

  // --------------------------------------------------
  // LOADING SCREEN
  // --------------------------------------------------

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

  // --------------------------------------------------
  // MAIN INTERVIEW UI
  // --------------------------------------------------

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
              Your interview will start in fullscreen mode.
              Leaving fullscreen will pause the interview and
              trigger a warning.
            </p>

            <p className="text-slate-400 text-sm mb-6">
              You have two warnings. If you do not return within
              8 seconds, or exit fullscreen for a third time,
              the interview will be terminated.
            </p>

            {error && (
              <p className="text-red-300 text-sm mb-4">
                {error}
              </p>
            )}

            {permissionError && (
              <p className="text-red-300 text-sm mb-4">
                {permissionError}
              </p>
            )}

            <div className="text-sm text-slate-400 mb-5 space-y-2">
              <p>
                Camera: {cameraEnabled ? "Ready" : "Not available"}
              </p>

              <p>
                Microphone: {micEnabled ? "Ready" : "Not available"}
              </p>
            </div>

            <button
              onClick={enterFullscreen}
              disabled={
                Boolean(error) ||
                Boolean(permissionError) ||
                !cameraEnabled ||
                !micEnabled ||
                !question
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
              Your interview is paused. Return to fullscreen
              immediately to continue.
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
              If the countdown reaches zero, your interview
              will be terminated.
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

        {/* CANDIDATE AND TIMER */}

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

        {/* ERRORS */}

        {error && (
          <div className="mb-5 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 flex gap-2">
            <AlertCircle size={20} />
            {error}
          </div>
        )}

        {permissionError && (
          <div className="mb-5 p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-yellow-200">
            {permissionError}
          </div>
        )}

        {/* MAIN GRID */}

        <div className="grid lg:grid-cols-2 gap-6">

          {/* CAMERA */}

          <section className="bg-[#11182c] border border-white/10 rounded-2xl p-5">

            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">
                Candidate Camera
              </h3>
            </div>

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

            <div className="flex justify-center gap-3 mt-5 flex-wrap">

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
              Camera and microphone controls are locked during
              the interview. Camera preview is active; video is
              not recorded or stored by this component.
            </p>

          </section>

          {/* QUESTION AND ANSWER */}

          <section className="bg-[#11182c] border border-white/10 rounded-2xl p-6">

            <div className="flex items-center justify-between mb-5">
              <span className="text-purple-400 text-sm font-semibold">
                INTERVIEW QUESTION
              </span>

              <span className="text-slate-400 text-sm">
                Question {questionNumber}
              </span>
            </div>

            <div className="bg-[#211b46] border border-purple-500/20 rounded-xl p-6 mb-6">

              <p className="text-xs text-purple-300 mb-3">
                {stage}
              </p>

              <h2 className="text-xl md:text-2xl font-semibold leading-relaxed">
                {question || "Waiting for the next question..."}
              </h2>

            </div>

            {/* VOICE RESPONSE */}

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
                    ? "Return to fullscreen to continue."
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
