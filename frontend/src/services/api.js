const BASE_URL = "http://127.0.0.1:8000";

export const registerUser = async (userName) => {
  const response = await fetch(`${BASE_URL}/users/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_name: userName, user_pdf_name: null }),
  });
  if (!response.ok) throw new Error("Registration failed");
  return await response.json();
};

export const uploadPdf = async (file, userId, userName) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  formData.append("user_name", userName);

  const response = await fetch(`${BASE_URL}/upload/`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) throw new Error("Upload failed");
  return await response.json();
};