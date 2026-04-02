import React from "react";
import {
  View,
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

interface PrimaryButtonProps {
  onPress: () => void;
  title: string;
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  icon?: string;
}

export const PrimaryButton: React.FC<PrimaryButtonProps> = ({
  onPress,
  title,
  loading = false,
  disabled = false,
  style,
  textStyle,
  icon,
}) => {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
    >
      <LinearGradient
        colors={disabled ? ["#4a4a4a", "#2a2a2a"] : ["#c5a059", "#b8944e"]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.button, style]}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#050505" />
        ) : (
          <Text style={[styles.buttonText, textStyle]}>
            {icon && `${icon} `}
            {title}
          </Text>
        )}
      </LinearGradient>
    </TouchableOpacity>
  );
};

interface SecondaryButtonProps {
  onPress: () => void;
  title: string;
  disabled?: boolean;
  style?: ViewStyle;
}

export const SecondaryButton: React.FC<SecondaryButtonProps> = ({
  onPress,
  title,
  disabled = false,
  style,
}) => {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.8}
      style={[styles.secondaryButton, disabled && styles.disabled, style]}
    >
      <Text style={styles.secondaryButtonText}>{title}</Text>
    </TouchableOpacity>
  );
};

interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  visible,
  message = "Processing...",
}) => {
  if (!visible) return null;

  return (
    <View style={styles.loadingOverlay}>
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#c5a059" />
        <Text style={styles.loadingText}>{message}</Text>
      </View>
    </View>
  );
};

interface StatusBannerProps {
  type: "success" | "error" | "info" | "warning";
  message: string;
  onDismiss?: () => void;
}

export const StatusBanner: React.FC<StatusBannerProps> = ({
  type,
  message,
  onDismiss,
}) => {
  const backgroundColor = {
    success: "#10b981",
    error: "#ef4444",
    info: "#3b82f6",
    warning: "#f59e0b",
  };

  const icon = {
    success: "✅",
    error: "❌",
    info: "ℹ️",
    warning: "⚠️",
  };

  return (
    <TouchableOpacity
      onPress={onDismiss}
      activeOpacity={0.8}
      style={[styles.banner, { backgroundColor: backgroundColor[type] }]}
    >
      <Text style={styles.bannerText}>
        {icon[type]} {message}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 8,
    elevation: 5,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  buttonText: {
    fontSize: 16,
    fontWeight: "600",
    color: "#050505",
    textAlign: "center",
  },
  secondaryButton: {
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#c5a059",
    alignItems: "center",
    justifyContent: "center",
    marginVertical: 8,
  },
  secondaryButtonText: {
    fontSize: 14,
    fontWeight: "600",
    color: "#c5a059",
  },
  disabled: {
    opacity: 0.5,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(5, 5, 5, 0.7)",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1000,
  },
  loadingContainer: {
    backgroundColor: "#1a1a1a",
    borderRadius: 16,
    padding: 24,
    alignItems: "center",
    minWidth: "60%",
    borderWidth: 1,
    borderColor: "#c5a059",
  },
  loadingText: {
    marginTop: 16,
    fontSize: 14,
    color: "#c5a059",
    fontWeight: "500",
  },
  banner: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    marginVertical: 8,
    borderRadius: 8,
    justifyContent: "center",
  },
  bannerText: {
    fontSize: 14,
    color: "#fff",
    fontWeight: "500",
  },
});
