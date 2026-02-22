const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Registers a new user in the Supabase database.
 * @param {string} userName - The name to store.
 */
export const registerUser = async (userName) => {
  try {
    const response = await fetch(`${API_BASE_URL}/users/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_name: userName,
        user_pdf_name: null, 
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "Failed to connect to Coeus.");
    }

    return await response.json();
  } catch (error) {
    console.error("API Service Error:", error);
    throw error;
  }
};