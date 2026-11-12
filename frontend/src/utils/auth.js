import { getToken, clearAuth } from "./session";

export const getStoredToken = () => getToken();
export const clearStoredAuth = () => clearAuth();

