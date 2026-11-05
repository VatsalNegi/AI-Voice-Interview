
import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

// -----------------------------------------
// CREATE INTERVIEW
// -----------------------------------------

export const createInterview = async (data) => {
  const response = await api.post("/interviews/create", data);
  return response.data;
};

// -----------------------------------------
// START INTERVIEW
// -----------------------------------------

export const startInterview = async (sessionId) => {
  const response = await api.post(`/interviews/${sessionId}/start`);
  return response.data;
};

// -----------------------------------------
// SUBMIT CANDIDATE ANSWER
// -----------------------------------------

export const submitAnswer = async (sessionId, answer) => {
  const response = await api.post(`/interviews/${sessionId}/answer`, {
    answer_text: answer,
  });

  return response.data;
};

// -----------------------------------------
// GET INTERVIEW SESSION
// -----------------------------------------

export const getInterview = async (sessionId) => {
  const response = await api.get(`/interviews/${sessionId}`);
  return response.data;
};

// -----------------------------------------
// GET INTERVIEW REPORT
// -----------------------------------------

export const getInterviewReport = async (sessionId) => {
  const response = await api.get(`/interviews/${sessionId}/report`);
  return response.data;
};

// -----------------------------------------
// AI INTERVIEWER TEXT-TO-SPEECH
// -----------------------------------------

export const speakQuestion = async (text) => {
  try {
    const response = await api.post(
      "/voice/speak",
      { text },
      {
        responseType: "blob",
        timeout: 120000,
      }
    );

    if (!response.data || response.data.size === 0) {
      throw new Error("The voice service returned empty audio.");
    }

    return response.data;

  } catch (error) {
    let message = "Unable to generate interviewer voice.";

    if (error.response?.data instanceof Blob) {
      try {
        const errorText = await error.response.data.text();
        const errorData = JSON.parse(errorText);

        message =
          errorData.detail ||
          errorData.message ||
          message;
      } catch {
        message = "The voice server returned an unreadable error.";
      }
    } else if (error.response?.data?.detail) {
      message = error.response.data.detail;
    } else if (error.message) {
      message = error.message;
    }

    console.error("TTS Error:", message);

    throw new Error(message);
  }
};

export default api;
