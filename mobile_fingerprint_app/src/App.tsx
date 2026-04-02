import React, { useEffect } from "react";
import { LogBox } from "react-native";
import * as SplashScreen from "expo-splash-screen";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { RootNavigator } from "./navigation/Navigation";
import APIClient from "./services/apiClient";

// Suppress warnings
LogBox.ignoreLogs([
  "Non-serializable values were found in the navigation state",
  "Teamwork: This is a warning",
]);

// Keep the splash screen visible while we fetch resources
SplashScreen.preventAutoHideAsync();

export default function App() {
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      console.log("[APP] Initializing...");

      // Configure API client (update backend URL here if needed)
      const backendURL =
        process.env.EXPO_PUBLIC_BACKEND_URL ||
        "https://biometric-backend-app.kindstone-7b8f6cd7.southeastasia.azurecontainerapps.io/api";
      APIClient.setBackendURL(backendURL);

      console.log("[APP] ✅ Initialization complete");
    } catch (error) {
      console.error("[APP] Initialization error:", error);
    } finally {
      // Hide the splash screen once initialization is done
      await SplashScreen.hideAsync();
    }
  };

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <RootNavigator />
    </GestureHandlerRootView>
  );
}
