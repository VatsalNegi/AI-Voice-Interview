
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import {
  Camera,
  CameraOff,
  Mic,
  MicOff,
  Send,
  Clock,
  BrainCircuit,
  CheckCircle,
  AlertCircle,
  Loader2,
  Volume2,
  Square,
  Mic2,
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

  // Controls whether the candidate still wants recognition active
  const listeningWantedRef = useRef(false);

  // Keeps the final recognized transcript across recognition restarts
  const transcriptRef = useRef("");

  // Prevents stale state inside asynchronous recognition callbacks
  const micEnabledRef = useRef(false);
  const submittingRef = useRef(false);
  const completedRef = useRef(false);


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


  // =========================================
  // CAMERA AND MICROPHONE INITIALIZATION
  // =========================================

  useEffect(() => {
    let active = true;

    async function initializeMedia() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });

        if (!active) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }

        setCameraEnabled(true);
        setMicEnabled(true);
        micEnabledRef.current = true;

      } catch (err) {
        console.error("Media permission error:", err);

        setPermissionError(
          "Camera or microphone access was denied. Please allow access in your browser settings."
        );
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
        "Please enable your microphone before answering."
      );
      return;
    }

    if (submittingRef.current || completedRef.current) {
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
        completedRef.current
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
            "Microphone permission denied. Please allow microphone access in your browser."
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
          !completedRef.current
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
              !completedRef.current
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
          !completedRef.current
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
    if (completed || loading) return;

    const timer = setInterval(() => {
      setSecondsElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(timer);

  }, [completed, loading]);


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
    if (!question || loading || completed) return;

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

            // Start candidate speech recognition
            startListening();
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
              "Click Play Question to hear the interviewer."
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
            "Unable to generate interviewer voice. You can still type your answer."
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

  }, [question, loading, completed]);


  // =========================================
  // REPLAY INTERVIEW QUESTION
  // =========================================

  const handleReplayQuestion = async () => {
    if (!audioRef.current) return;

    // Stop candidate recognition while interviewer speaks
    stopListening();

    try {
      audioRef.current.currentTime = 0;

      await audioRef.current.play();

      setVoiceStatus("speaking");
      setSpeechError("");

    } catch (err) {
      console.error("Replay failed:", err);

      setVoiceStatus("error");

      setSpeechError(
        "Unable to replay the interview question."
      );
    }
  };


  // =========================================
  // CAMERA TOGGLE
  // =========================================

  const toggleCamera = () => {
    if (!streamRef.current) return;

    const videoTrack =
      streamRef.current.getVideoTracks()[0];

    if (videoTrack) {
      videoTrack.enabled = !videoTrack.enabled;

      setCameraEnabled(videoTrack.enabled);
    }
  };


  // =========================================
  // MICROPHONE TOGGLE
  // =========================================

  const toggleMicrophone = () => {
    if (!streamRef.current) return;

    const audioTrack =
      streamRef.current.getAudioTracks()[0];

    if (audioTrack) {
      audioTrack.enabled = !audioTrack.enabled;

      setMicEnabled(audioTrack.enabled);
      micEnabledRef.current = audioTrack.enabled;

      if (!audioTrack.enabled) {
        stopListening();
        setSpeechError(
          "Microphone is disabled. Enable it to continue speaking."
        );
      }
    }
  };


  // =========================================
  // SUBMIT CANDIDATE ANSWER
  // =========================================

  const handleSubmitAnswer = async (event) => {
    event.preventDefault();

    if (
      !answer.trim() ||
      submitting ||
      completed ||
      isListening
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
        answer.trim()
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

              <span className="text-xs text-red-400">
                ● RECORDING NOT ENABLED
              </span>

            </div>


            {/* VIDEO PREVIEW */}

            <div className="bg-black rounded-xl overflow-hidden aspect-video flex items-center justify-center">

              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className={`w-full h-full object-cover ${
                  cameraEnabled ? "" : "hidden"
                }`}
              />

              {!cameraEnabled && (
                <div className="text-center text-slate-500">

                  <CameraOff size={45} className="mx-auto mb-3" />

                  Camera unavailable

                </div>
              )}

            </div>


            {/* CAMERA AND MICROPHONE BUTTONS */}

            <div className="flex justify-center gap-5 mt-5">

              <button
                onClick={toggleCamera}
                type="button"
                className="p-4 bg-[#202b42] hover:bg-purple-700 rounded-full"
                title="Toggle camera"
              >
                {cameraEnabled ? <Camera /> : <CameraOff />}
              </button>


              <button
                onClick={toggleMicrophone}
                type="button"
                className="p-4 bg-[#202b42] hover:bg-purple-700 rounded-full"
                title="Toggle microphone"
              >
                {micEnabled ? <Mic /> : <MicOff />}
              </button>

            </div>


            <p className="text-xs text-center text-slate-500 mt-4">

              Camera preview and microphone access are enabled.

              Video recording is not implemented yet.

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


              {/* AI VOICE CONTROL */}

              <div className="mt-5 flex flex-wrap items-center gap-3">

                <button
                  type="button"
                  onClick={handleReplayQuestion}
                  disabled={
                    !audioRef.current ||
                    voiceStatus === "generating" ||
                    !question
                  }
                  className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-5 py-3 rounded-xl flex items-center gap-2 font-medium"
                >

                  <Volume2 size={18} />

                  {voiceStatus === "generating"
                    ? "Generating Voice..."
                    : voiceStatus === "speaking"
                    ? "Speaking..."
                    : "Play Question"}

                </button>


                <span className="text-sm text-slate-400">

                  {voiceStatus === "idle" &&
                    "Waiting for voice"}

                  {voiceStatus === "generating" &&
                    "Preparing interviewer voice"}

                  {voiceStatus === "speaking" &&
                    "AI interviewer is speaking"}

                  {voiceStatus === "ready" &&
                    "Voice ready"}

                  {voiceStatus === "error" &&
                    "Voice unavailable"}

                </span>

              </div>

            </div>


            {/* ANSWER FORM */}

            <form onSubmit={handleSubmitAnswer}>

              <div className="flex justify-between items-center mb-3">

                <label className="block text-sm font-medium">
                  Your Answer
                </label>

                {isListening && (
                  <span className="flex items-center gap-2 text-red-400 text-sm">

                    <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />

                    Listening...

                  </span>
                )}

              </div>


              {/* ANSWER TEXTAREA */}

              <textarea
                value={answer}
                onChange={(event) => {
                  setAnswer(event.target.value);
                  transcriptRef.current = event.target.value;
                }}
                placeholder={
                  isListening
                    ? "Speak your answer. Your recognized speech will appear here..."
                    : "Your recognized answer will appear here, or type your answer..."
                }
                rows={9}
                maxLength={10000}
                required
                disabled={submitting || !question}
                className="w-full bg-[#07091b] border border-white/10 rounded-xl p-4 text-white placeholder-slate-500 outline-none focus:border-purple-500 resize-none"
              />


              {/* SPEECH ERROR */}

              {speechError && (
                <div className="mt-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-sm flex gap-2">

                  <AlertCircle size={18} className="shrink-0" />

                  {speechError}

                </div>
              )}


              {/* SPEECH CONTROLS */}

              <div className="flex flex-wrap gap-3 mt-4">

                {!isListening ? (

                  <button
                    type="button"
                    onClick={startListening}
                    disabled={
                      !speechSupported ||
                      !micEnabled ||
                      submitting ||
                      !question
                    }
                    className="flex-1 bg-[#202b42] hover:bg-purple-700 disabled:opacity-50 px-4 py-3 rounded-xl flex justify-center items-center gap-2 font-semibold"
                  >

                    <Mic2 size={19} />

                    Start Speaking

                  </button>

                ) : (

                  <button
                    type="button"
                    onClick={stopListening}
                    className="flex-1 bg-red-600 hover:bg-red-700 px-4 py-3 rounded-xl flex justify-center items-center gap-2 font-semibold"
                  >

                    <Square size={17} />

                    Stop Answer

                  </button>

                )}

              </div>


              {/* BROWSER SUPPORT */}

              {!speechSupported && (
                <p className="text-xs text-yellow-300 mt-3">

                  Use the latest Chrome or Edge browser for speech recognition.
                  You can still type your answer.

                </p>
              )}


              {/* ANSWER COUNTER */}

              <div className="flex justify-between items-center mt-4 mb-5 text-xs text-slate-500">

                <span>
                  {isListening
                    ? "Speak clearly. Recognition will restart if the browser stops it."
                    : "Review your answer before submitting."}
                </span>

                <span>
                  {answer.length}/10000
                </span>

              </div>


              {/* SUBMIT BUTTON */}

              <button
                type="submit"
                disabled={
                  !answer.trim() ||
                  submitting ||
                  isListening ||
                  !question
                }
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed py-4 rounded-xl font-semibold flex justify-center items-center gap-2"
              >

                {submitting ? (

                  <>
                    <Loader2 className="animate-spin" size={20} />

                    Evaluating Answer...
                  </>

                ) : (

                  <>
                    Submit Answer

                    <Send size={18} />
                  </>

                )}

              </button>

            </form>

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
