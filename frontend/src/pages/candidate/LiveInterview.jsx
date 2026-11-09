
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
} from "../../services/api";


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

  const recognitionRef = useRef(null);
  const restartTimerRef = useRef(null);
  const vadIntervalRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const speechStartedRef = useRef(false);
  const silenceStartedAtRef = useRef(null);
  const autoSubmitLockRef = useRef(false);

  // Controls whether the candidate still wants recognition active
  const listeningWantedRef = useRef(false);

  // Keeps the final recognized transcript across recognition restarts
  const transcriptRef = useRef("");

  // Prevents stale state inside asynchronous recognition callbacks
  const micEnabledRef = useRef(false);
  const submittingRef = useRef(false);
  const completedRef = useRef(false);

  // Fullscreen proctoring refs.
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

  // Fullscreen proctoring states.
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

  /*
    idle
    generating
    speaking
    ready
    error
  */


  // =========================================
  // SPEECH RECOGNITION STATES
  // =========================================

  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const [silenceCountdown, setSilenceCountdown] = useState(4);


  // Keep refs synchronized with current state
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
  // FULLSCREEN PROCTORING
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

    // Stop local media immediately. The backend endpoint is added separately.
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    try {
      const baseUrl =
        import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

      const response = await fetch(
        `${baseUrl}/interviews/${sessionId}/terminate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            reason,
            violation_count: violationCountRef.current,
          }),
        }
      );

      if (!response.ok) {
        console.error(
          "Backend termination request failed:",
          response.status,
          await response.text()
        );
      }
    } catch (err) {
      console.error("Unable to persist interview termination:", err);
    }
  };

  const enterFullscreenAndStart = async () => {
    try {
      if (!document.fullscreenElement) {
        if (!document.documentElement.requestFullscreen) {
          throw new Error("Fullscreen is not supported by this browser.");
        }

        await document.documentElement.requestFullscreen();
      }

      if (!document.fullscreenElement) {
        throw new Error("Please allow fullscreen mode to start the interview.");
      }

      interviewStartedRef.current = true;
      setProctoringReady(true);
      setProctoringMessage("");
    } catch (err) {
      console.error("Fullscreen request failed:", err);
      setProctoringMessage(
        err.message ||
          "Fullscreen could not be enabled. Please use a supported browser and try again."
      );
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      if (
        !interviewStartedRef.current ||
        completedRef.current ||
        terminationRef.current
      ) {
        return;
      }

      if (!document.fullscreenElement) {
        // Ignore duplicate fullscreenchange events while a warning is active.
        if (pausedRef.current) return;

        const nextViolation = violationCountRef.current + 1;
        violationCountRef.current = nextViolation;
        setViolationCount(nextViolation);

        stopInterviewActivity();

        if (nextViolation > 2) {
          terminateInterview(
            "Interview terminated because the fullscreen warning limit was exceeded."
          );
          return;
        }

        pausedRef.current = true;
        setIsPaused(true);
        setFullscreenWarning(true);
        setCountdown(8);

        countdownTimerRef.current = setTimeout(() => {
          countdownTimerRef.current = null;

          if (
            pausedRef.current &&
            !document.fullscreenElement &&
            !terminationRef.current
          ) {
            terminateInterview(
              "Interview terminated because fullscreen was not restored within 8 seconds."
            );
          }
        }, 8000);
      } else if (pausedRef.current) {
        if (countdownTimerRef.current) {
          clearTimeout(countdownTimerRef.current);
          countdownTimerRef.current = null;
        }

        pausedRef.current = false;
        setIsPaused(false);
        setFullscreenWarning(false);
        setCountdown(8);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      if (countdownTimerRef.current) {
        clearTimeout(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!isPaused || !fullscreenWarning) return;

    const interval = setInterval(() => {
      setCountdown((previous) => Math.max(0, previous - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [isPaused, fullscreenWarning]);

  // =========================================
  // CAMERA AND MICROPHONE INITIALIZATION
  // =========================================

  useEffect(() => {
    let active = true;

    async function initializeMedia() {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error(
            "Camera access is unavailable. Open this page using localhost or HTTPS in a supported browser."
          );
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: true,
        });

        if (!active) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        const videoTrack = stream.getVideoTracks()[0];
        const audioTrack = stream.getAudioTracks()[0];

        setCameraEnabled(Boolean(videoTrack?.enabled));
        setMicEnabled(Boolean(audioTrack?.enabled));
        micEnabledRef.current = Boolean(audioTrack?.enabled);
      } catch (err) {
        console.error("Media permission error:", err);

        if (active) {
          setPermissionError(
            err.name === "NotAllowedError"
              ? "Camera or microphone permission was denied. Allow access in your browser settings and reload the interview."
              : err.message ||
                "Unable to access your camera or microphone. Check that your devices are connected and not being used by another application."
          );
        }
      }
    }

    initializeMedia();

    return () => {
      active = false;

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, []);

  // Attach the stream after the interview UI (and video element) has mounted.
  // The loading screen initially prevents the video element from existing.
  useEffect(() => {
    const video = videoRef.current;
    const stream = streamRef.current;

    if (!video || !stream) return;

    video.srcObject = stream;

    const playVideo = async () => {
      try {
        await video.play();
        console.log("Camera preview started successfully.");
      } catch (err) {
        console.error("Camera preview playback failed:", err);
        setPermissionError(
          "The camera is connected, but the preview could not start. Try refreshing the page or checking browser camera permissions."
        );
      }
    };

    if (video.readyState >= 1) {
      playVideo();
    } else {
      video.onloadedmetadata = playVideo;
    }

    return () => {
      video.onloadedmetadata = null;
    };
  }, [loading, cameraEnabled]);


  // =========================================
  // CHECK SPEECH RECOGNITION SUPPORT
  // =========================================

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    setSpeechSupported(Boolean(SpeechRecognition));

    if (!SpeechRecognition) {
      setSpeechError(
        "Speech recognition is not supported. Please use the latest Chrome or Edge."
      );
    }

  }, []);


  // =========================================
  // STOP SPEECH RECOGNITION
  // =========================================

  const stopListening = () => {
    // Stop silence detection together with speech recognition.
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    speechStartedRef.current = false;
    silenceStartedAtRef.current = null;
    setSilenceCountdown(4);

    // Explicitly disable automatic restarting
    listeningWantedRef.current = false;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    const recognition = recognitionRef.current;

    recognitionRef.current = null;

    if (recognition) {
      try {
        recognition.stop();
      } catch (err) {
        console.log("Recognition already stopped.");
      }
    }

    setIsListening(false);
  };


  // =========================================
  // AUTOMATIC SILENCE DETECTION (4 SECONDS)
  // =========================================

  const startSilenceDetection = () => {
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }

    const stream = streamRef.current;
    if (!stream) return;

    try {
      const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;

      if (!AudioContextClass) {
        setSpeechError("Automatic silence detection is not supported in this browser.");
        return;
      }

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextClass();
        analyserRef.current = audioContextRef.current.createAnalyser();
        analyserRef.current.fftSize = 2048;

        const source = audioContextRef.current.createMediaStreamSource(stream);
        source.connect(analyserRef.current);
      }

      const context = audioContextRef.current;
      const analyser = analyserRef.current;

      if (context.state === "suspended") {
        context.resume();
      }

      const samples = new Uint8Array(analyser.fftSize);
      speechStartedRef.current = false;
      silenceStartedAtRef.current = null;
      autoSubmitLockRef.current = false;
      setSilenceCountdown(4);

      vadIntervalRef.current = setInterval(() => {
        if (
          submittingRef.current ||
          completedRef.current ||
          pausedRef.current ||
          !proctoringReady ||
          !listeningWantedRef.current
        ) {
          return;
        }

        analyser.getByteTimeDomainData(samples);

        let sumSquares = 0;
        for (let i = 0; i < samples.length; i++) {
          const normalized = (samples[i] - 128) / 128;
          sumSquares += normalized * normalized;
        }

        const rms = Math.sqrt(sumSquares / samples.length);
        const now = Date.now();

        // A conservative threshold filters ordinary microphone noise.
        if (rms > 0.025) {
          speechStartedRef.current = true;
          silenceStartedAtRef.current = null;
          setSilenceCountdown(4);
          return;
        }

        // Do not submit until the candidate has actually spoken.
        if (!speechStartedRef.current) return;

        if (silenceStartedAtRef.current === null) {
          silenceStartedAtRef.current = now;
        }

        const silentFor = now - silenceStartedAtRef.current;
        const remaining = Math.max(0, 4 - Math.floor(silentFor / 1000));
        setSilenceCountdown(remaining);

        if (silentFor >= 4000 && !autoSubmitLockRef.current) {
          autoSubmitLockRef.current = true;
          clearInterval(vadIntervalRef.current);
          vadIntervalRef.current = null;

          const finalAnswer = transcriptRef.current.trim();
          if (finalAnswer) {
            listeningWantedRef.current = false;
            setIsListening(false);
            handleSubmitAnswer();
          } else {
            autoSubmitLockRef.current = false;
            speechStartedRef.current = false;
            silenceStartedAtRef.current = null;
            setSpeechError("I couldn't recognize your answer. Please speak again.");
            startListening();
          }
        }
      }, 100);
    } catch (err) {
      console.error("Silence detection initialization failed:", err);
      setSpeechError("Unable to start automatic voice detection. Please refresh and try again.");
    }
  };


  // =========================================
  // START SPEECH RECOGNITION
  // =========================================

  const startListening = () => {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setSpeechError(
        "Your browser does not support speech recognition. Please use Chrome or Edge."
      );
      return;
    }

    if (!micEnabledRef.current) {
      setSpeechError(
        "The required microphone is unavailable. Please check browser permissions."
      );
      return;
    }

    if (
      submittingRef.current ||
      completedRef.current ||
      pausedRef.current ||
      !proctoringReady
    ) {
      return;
    }

    if (listeningWantedRef.current) {
      return;
    }

    // Cancel any previous recognition instance
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (err) {
        console.log("Previous recognition already stopped.");
      }

      recognitionRef.current = null;
    }

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    // Preserve existing text if the candidate resumes speaking
    transcriptRef.current = answer.trim();

    listeningWantedRef.current = true;

    setSpeechError("");
    setError("");
    setIsListening(true);

    // -----------------------------------------
    // CREATE A NEW RECOGNITION INSTANCE
    // -----------------------------------------

    const startRecognitionInstance = () => {
      if (
        !listeningWantedRef.current ||
        !micEnabledRef.current ||
        submittingRef.current ||
        completedRef.current ||
        pausedRef.current ||
        !proctoringReady
      ) {
        setIsListening(false);
        return;
      }

      const recognition = new SpeechRecognition();

      recognition.lang = "en-IN";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognitionRef.current = recognition;


      // ---------------------------------------
      // RECOGNITION STARTED
      // ---------------------------------------

      recognition.onstart = () => {
        console.log("Speech recognition started.");

        setIsListening(true);
        setSpeechError("");
      };


      // ---------------------------------------
      // SPEECH RESULTS
      // ---------------------------------------

      recognition.onresult = (event) => {
        let interimTranscript = "";

        for (
          let i = event.resultIndex;
          i < event.results.length;
          i++
        ) {
          const result = event.results[i];

          const recognizedText = result[0].transcript.trim();

          if (result.isFinal && recognizedText) {
            transcriptRef.current = [
              transcriptRef.current,
              recognizedText,
            ]
              .filter(Boolean)
              .join(" ");

          } else if (recognizedText) {
            interimTranscript += recognizedText + " ";
          }
        }

        const completeTranscript = [
          transcriptRef.current,
          interimTranscript.trim(),
        ]
          .filter(Boolean)
          .join(" ");

        setAnswer(completeTranscript);
        if (completeTranscript.trim()) speechStartedRef.current = true;
      };


      // ---------------------------------------
      // RECOGNITION ERRORS
      // ---------------------------------------

      recognition.onerror = (event) => {
        console.error(
          "Speech recognition error:",
          event.error
        );

        if (
          event.error === "not-allowed" ||
          event.error === "service-not-allowed"
        ) {
          listeningWantedRef.current = false;

          setIsListening(false);

          setSpeechError(
            "Microphone permission denied. Allow microphone access and reload the interview."
          );

        } else if (event.error === "audio-capture") {
          listeningWantedRef.current = false;

          setIsListening(false);

          setSpeechError(
            "No working microphone was detected."
          );

        } else if (event.error === "no-speech") {
          console.log(
            "No speech detected. Recognition will restart."
          );

        } else if (event.error === "network") {
          console.warn(
            "Speech recognition network issue. Attempting restart."
          );

          setSpeechError(
            "Speech service temporarily disconnected. Reconnecting..."
          );

        } else if (event.error !== "aborted") {
          console.warn(
            "Temporary speech recognition error:",
            event.error
          );
        }
      };


      // ---------------------------------------
      // RECOGNITION ENDED
      // ---------------------------------------

      recognition.onend = () => {
        console.log("Speech recognition session ended.");

        // Ignore events from old recognition instances
        if (recognitionRef.current !== recognition) {
          return;
        }

        recognitionRef.current = null;

        // Restart only if the candidate has not pressed Stop Answer
        if (
          listeningWantedRef.current &&
          micEnabledRef.current &&
          !submittingRef.current &&
          !completedRef.current &&
          !pausedRef.current &&
          proctoringReady
        ) {
          console.log(
            "Recognition stopped unexpectedly. Restarting..."
          );

          setIsListening(true);

          restartTimerRef.current = setTimeout(() => {
            restartTimerRef.current = null;

            if (
              listeningWantedRef.current &&
              micEnabledRef.current &&
              !submittingRef.current &&
              !completedRef.current &&
              !pausedRef.current &&
              proctoringReady
            ) {
              startRecognitionInstance();
            }

          }, 700);

        } else {
          setIsListening(false);
        }
      };


      // ---------------------------------------
      // START THE RECOGNITION INSTANCE
      // ---------------------------------------

      try {
        recognition.start();

      } catch (err) {
        console.error(
          "Unable to start recognition:",
          err
        );

        if (recognitionRef.current === recognition) {
          recognitionRef.current = null;
        }

        // A restart error can be transient. Retry while listening is wanted.
        if (
          listeningWantedRef.current &&
          micEnabledRef.current &&
          !submittingRef.current &&
          !completedRef.current &&
          !pausedRef.current &&
          proctoringReady
        ) {
          restartTimerRef.current = setTimeout(() => {
            restartTimerRef.current = null;

            if (listeningWantedRef.current) {
              startRecognitionInstance();
            }
          }, 1200);

        } else {
          setIsListening(false);
          setSpeechError(
            "Unable to start speech recognition. Please try again."
          );
        }
      }
    };

    startRecognitionInstance();
  };


  // =========================================
  // INTERVIEW TIMER
  // =========================================

  useEffect(() => {
    if (completed || loading || !proctoringReady || isPaused || terminated) return;

    const timer = setInterval(() => {
      setSecondsElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(timer);

  }, [completed, loading, proctoringReady, isPaused, terminated]);


  // =========================================
  // FORMAT TIMER
  // =========================================

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    return `${String(minutes).padStart(2, "0")}:${String(
      remainingSeconds
    ).padStart(2, "0")}`;
  };


  // =========================================
  // LOAD INTERVIEW SESSION
  // =========================================

  useEffect(() => {
    let active = true;

    async function loadInterview() {
      if (!sessionId) {
        setError("Interview session ID is missing.");
        setLoading(false);
        return;
      }

      try {
        const data = await getInterview(sessionId);

        if (!active) return;

        console.log("LOADED SESSION:", data);

        if (data.status === "completed") {
          setCompleted(true);
        }

        const currentQuestion =
          data.current_question?.question ||
          data.current_question ||
          data.question ||
          "";

        setQuestion(
          typeof currentQuestion === "string"
            ? currentQuestion
            : ""
        );

        setStage(data.current_stage || "INTRO");

      } catch (err) {
        if (!active) return;

        console.error(err);

        setError(
          err.response?.data?.detail ||
          "Unable to load interview session."
        );

      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadInterview();

    return () => {
      active = false;
    };

  }, [sessionId]);


  // =========================================
  // AI INTERVIEWER TEXT-TO-SPEECH
  // =========================================

  useEffect(() => {
    if (
      !question ||
      loading ||
      completed ||
      !proctoringReady ||
      isPaused ||
      terminated
    ) return;

    let cancelled = false;

    async function generateAndPlayVoice() {
      try {
        setVoiceStatus("generating");

        setSpeechError("");

        console.log(
          "Generating AI interviewer voice:",
          question
        );

        const audioBlob = await speakQuestion(question);

        if (cancelled) return;

        const audioUrl = URL.createObjectURL(audioBlob);

        audioUrlRef.current = audioUrl;

        const audio = new Audio(audioUrl);

        audioRef.current = audio;


        // ---------------------------------------
        // AI FINISHED SPEAKING
        // ---------------------------------------

        audio.onended = () => {
          if (!cancelled) {
            setVoiceStatus("ready");

            console.log(
              "AI interviewer finished speaking."
            );

            // Start candidate speech recognition and silence detection
            startListening();
            startSilenceDetection();
          }
        };


        // ---------------------------------------
        // AUDIO ERROR
        // ---------------------------------------

        audio.onerror = () => {
          if (!cancelled) {
            setVoiceStatus("error");

            setSpeechError(
              "Unable to play the AI interviewer voice."
            );
          }
        };


        // ---------------------------------------
        // PLAY AUDIO
        // ---------------------------------------

        setVoiceStatus("speaking");

        try {
          await audio.play();

          console.log(
            "AI interviewer is speaking."
          );

        } catch (playError) {
          console.warn(
            "Automatic playback blocked:",
            playError
          );

          if (!cancelled) {
            setVoiceStatus("ready");

            setSpeechError(
              "Automatic playback was blocked. Please refresh the interview and allow audio playback."
            );
          }
        }

      } catch (err) {
        console.error(
          "TTS generation failed:",
          err
        );

        if (!cancelled) {
          setVoiceStatus("error");

          setSpeechError(
            "Unable to generate interviewer voice. Please refresh the interview or contact the recruiter."
          );
        }
      }
    }

    generateAndPlayVoice();

    return () => {
      cancelled = true;

      if (audioRef.current) {
        audioRef.current.pause();

        audioRef.current.onended = null;
        audioRef.current.onerror = null;

        audioRef.current = null;
      }

      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };

  }, [question, loading, completed, proctoringReady, isPaused, terminated]);


  // =========================================
  // SUBMIT CANDIDATE ANSWER
  // =========================================

  const handleSubmitAnswer = async () => {
    const finalAnswer = transcriptRef.current.trim() || answer.trim();

    if (
      !finalAnswer ||
      submittingRef.current ||
      completedRef.current ||
      pausedRef.current ||
      !proctoringReady ||
      terminationRef.current
    ) {
      return;
    }

    // Stop speech recognition before submitting
    stopListening();

    // Stop current audio
    if (audioRef.current) {
      audioRef.current.pause();
    }

    submittingRef.current = true;

    setSubmitting(true);
    setError("");
    setSpeechError("");

    try {
      const response = await submitAnswer(
        sessionId,
        finalAnswer
      );

      console.log(
        "ANSWER API RESPONSE:",
        response
      );

      const result = response.result || response;

      const nextQuestion =
        result.next_question?.question ||
        result.next_question ||
        result.current_question?.question ||
        result.current_question ||
        result.question ||
        "";

      const decision =
        result.decision ||
        result.decision_evaluation?.decision ||
        result.action ||
        "";

      const status = result.status || "";


      // ---------------------------------------
      // INTERVIEW COMPLETED
      // ---------------------------------------

      if (
        status === "completed" ||
        result.interview_completed === true ||
        decision === "COMPLETED"
      ) {
        completedRef.current = true;

        setCompleted(true);
        setQuestion("");
        setAnswer("");

        return;
      }


      // ---------------------------------------
      // NEXT QUESTION
      // ---------------------------------------

      if (
        typeof nextQuestion === "string" &&
        nextQuestion.trim()
      ) {
        setQuestion(nextQuestion);

        setQuestionNumber(
          (previous) => previous + 1
        );

      } else if (
        decision === "NEXT_QUESTION" ||
        decision === "FOLLOW_UP"
      ) {
        const updatedSession =
          await getInterview(sessionId);

        const updatedQuestion =
          updatedSession.current_question?.question ||
          updatedSession.current_question ||
          "";

        if (typeof updatedQuestion === "string") {
          setQuestion(updatedQuestion);
        }

        setStage(
          updatedSession.current_stage || stage
        );

        setQuestionNumber(
          (previous) => previous + 1
        );

      } else {
        throw new Error(
          "The backend did not return the next interview question."
        );
      }

      // Clear the previous candidate transcript
      transcriptRef.current = "";
      speechStartedRef.current = false;
      silenceStartedAtRef.current = null;
      autoSubmitLockRef.current = false;
      setSilenceCountdown(4);
      setAnswer("");

    } catch (err) {
      console.error(err);

      setError(
        err.response?.data?.detail ||
        err.message ||
        "Unable to submit your answer. Please try again."
      );

    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };


  // =========================================
  // FINAL CLEANUP
  // =========================================

  useEffect(() => {
    return () => {
      listeningWantedRef.current = false;

      if (restartTimerRef.current) {
        clearTimeout(restartTimerRef.current);
      }

      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (err) {
          console.log("Recognition cleanup:", err);
        }

        recognitionRef.current = null;
      }

      if (vadIntervalRef.current) {
        clearInterval(vadIntervalRef.current);
        vadIntervalRef.current = null;
      }

      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }

      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    };
  }, []);


  // =========================================
  // TERMINATED INTERVIEW
  // =========================================

  if (terminated) {
    return (
      <div className="min-h-screen bg-[#07091b] text-white flex items-center justify-center p-6">
        <div className="max-w-xl w-full bg-[#11182c] border border-red-500/30 rounded-2xl p-10 text-center">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-5" />
          <h1 className="text-3xl font-bold mb-3">Interview Terminated</h1>
          <p className="text-slate-300 mb-3">{proctoringMessage}</p>
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
            <h2 className="text-2xl font-bold mb-3">Fullscreen Required</h2>
            <p className="text-slate-300 mb-4">
              Your interview will start in fullscreen mode. Leaving fullscreen
              will pause the interview and trigger a warning.
            </p>
            <p className="text-slate-400 text-sm mb-6">
              You have two warnings. If you do not return within 8 seconds,
              or exit fullscreen for a third time, the interview will be terminated.
            </p>
            {proctoringMessage && (
              <p className="text-yellow-300 text-sm mb-4">{proctoringMessage}</p>
            )}
            <button
              onClick={enterFullscreenAndStart}
              disabled={loading || Boolean(error) || Boolean(permissionError)}
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
            <h2 className="text-2xl font-bold mb-3">Return to Fullscreen</h2>
            <p className="text-slate-300 mb-5">
              Your interview is paused. Return to fullscreen immediately to continue.
            </p>
            <div className="text-5xl font-bold font-mono text-yellow-300 mb-5">
              00:{String(countdown).padStart(2, "0")}
            </div>
            <button
              onClick={async () => {
                try {
                  await document.documentElement.requestFullscreen();
                } catch (err) {
                  console.error("Could not restore fullscreen:", err);
                }
              }}
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


          {/* ================================= */}
          {/* CAMERA SECTION */}
          {/* ================================= */}

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


          {/* ================================= */}
          {/* QUESTION AND ANSWER SECTION */}
          {/* ================================= */}

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
                <span className="text-sm font-semibold">VOICE RESPONSE</span>
                {isListening ? (
                  <span className="flex items-center gap-2 text-red-400 text-sm">
                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                    Listening
                  </span>
                ) : submitting ? (
                  <span className="text-purple-300 text-sm">Evaluating answer...</span>
                ) : (
                  <span className="text-slate-400 text-sm">Waiting</span>
                )}
              </div>

              <div className="flex flex-col items-center text-center py-5">
                <div className={`w-20 h-20 rounded-full flex items-center justify-center mb-4 ${
                  isListening ? "bg-red-500/15 text-red-400" : "bg-purple-500/15 text-purple-300"
                }`}>
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
