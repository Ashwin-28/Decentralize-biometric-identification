import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  SafeAreaView,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { PrimaryButton, SecondaryButton } from "../components/Button";
import BiometricService from "../services/biometricService";
import APIClient from "../services/apiClient";

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation();
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [blockchainConnected, setBlockchainConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      // Check biometric availability
      const isBioAvailable = await BiometricService.isBiometricAvailable();
      setBiometricAvailable(isBioAvailable);

      // Check blockchain connection
      const isConnected = await APIClient.checkConnection();
      setBlockchainConnected(isConnected);
    } catch (error) {
      console.error("[HOME] Initialization error:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#c5a059" />
          <Text style={styles.loadingText}>Initializing...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Hero Section */}
        <LinearGradient
          colors={["#c5a059", "#b8944e"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.heroSection}
        >
          <Text style={styles.heroTitle}>🔐 Biometric Wallet</Text>
          <Text style={styles.heroSubtitle}>
            Decentralized Fingerprint Authentication
          </Text>
        </LinearGradient>

        {/* Status Cards */}
        <View style={styles.statusContainer}>
          <View
            style={[
              styles.statusCard,
              biometricAvailable ? styles.statusSuccess : styles.statusError,
            ]}
          >
            <Text style={styles.statusIcon}>
              {biometricAvailable ? "✅" : "❌"}
            </Text>
            <Text style={styles.statusLabel}>Biometric Sensor</Text>
            <Text style={styles.statusValue}>
              {biometricAvailable ? "Available" : "Not Available"}
            </Text>
          </View>

          <View
            style={[
              styles.statusCard,
              blockchainConnected ? styles.statusSuccess : styles.statusError,
            ]}
          >
            <Text style={styles.statusIcon}>
              {blockchainConnected ? "✅" : "❌"}
            </Text>
            <Text style={styles.statusLabel}>Blockchain</Text>
            <Text style={styles.statusValue}>
              {blockchainConnected ? "Connected" : "Disconnected"}
            </Text>
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>

          <LinearGradient
            colors={["#1a1a1a", "#0a0a0a"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.actionCard}
          >
            <View style={styles.actionContent}>
              <Text style={styles.actionIcon}>📋</Text>
              <View style={styles.actionText}>
                <Text style={styles.actionTitle}>Enrollment</Text>
                <Text style={styles.actionDescription}>
                  Register your fingerprint on blockchain
                </Text>
              </View>
            </View>
            <PrimaryButton
              onPress={() => navigation.navigate("Enroll" as never)}
              title="Start"
              icon="➜"
            />
          </LinearGradient>

          <LinearGradient
            colors={["#1a1a1a", "#0a0a0a"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.actionCard}
          >
            <View style={styles.actionContent}>
              <Text style={styles.actionIcon}>🔐</Text>
              <View style={styles.actionText}>
                <Text style={styles.actionTitle}>Authentication</Text>
                <Text style={styles.actionDescription}>
                  Verify your fingerprint against records
                </Text>
              </View>
            </View>
            <PrimaryButton
              onPress={() => navigation.navigate("Auth" as never)}
              title="Start"
              icon="➜"
            />
          </LinearGradient>
        </View>

        {/* Features */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Key Features</Text>

          <View style={styles.featureGrid}>
            <FeatureCard
              icon="🛡️"
              title="Secure"
              description="Encrypted fingerprint storage"
            />
            <FeatureCard
              icon="⚡"
              title="Fast"
              description="Instant biometric verification"
            />
            <FeatureCard
              icon="🌐"
              title="Decentralized"
              description="Blockchain-backed records"
            />
            <FeatureCard
              icon="📱"
              title="Mobile"
              description="Native Android app"
            />
          </View>
        </View>

        {/* Info Box */}
        <View style={styles.section}>
          <View style={styles.infoBox}>
            <Text style={styles.infoTitle}>System Status</Text>
            <View style={styles.infoDetail}>
              <Text style={styles.infoLabel}>Sensor Type:</Text>
              <Text style={styles.infoValue}>BiometricPrompt (Android)</Text>
            </View>
            <View style={styles.infoDetail}>
              <Text style={styles.infoLabel}>Connection:</Text>
              <Text
                style={[
                  styles.infoValue,
                  { color: blockchainConnected ? "#10b981" : "#ef4444" },
                ]}
              >
                {blockchainConnected ? "Online" : "Offline"}
              </Text>
            </View>
            <PrimaryButton
              onPress={initializeApp}
              title="Refresh Status"
              icon="🔄"
            />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

interface FeatureCardProps {
  icon: string;
  title: string;
  description: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({
  icon,
  title,
  description,
}) => {
  return (
    <View style={styles.featureCard}>
      <Text style={styles.featureIcon}>{icon}</Text>
      <Text style={styles.featureTitle}>{title}</Text>
      <Text style={styles.featureDescription}>{description}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#050505",
  },
  scrollContent: {
    paddingBottom: 20,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: "#c5a059",
  },
  heroSection: {
    paddingVertical: 32,
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: "700",
    color: "#050505",
    marginBottom: 4,
  },
  heroSubtitle: {
    fontSize: 14,
    color: "#1a1a1a",
  },
  statusContainer: {
    flexDirection: "row",
    paddingHorizontal: 16,
    marginBottom: 24,
    gap: 12,
  },
  statusCard: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: 1,
  },
  statusSuccess: {
    backgroundColor: "#0a2e0a",
    borderColor: "#10b981",
  },
  statusError: {
    backgroundColor: "#2e0a0a",
    borderColor: "#ef4444",
  },
  statusIcon: {
    fontSize: 24,
    marginBottom: 8,
  },
  statusLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#aaa",
    marginBottom: 4,
  },
  statusValue: {
    fontSize: 13,
    fontWeight: "700",
    color: "#fff",
  },
  section: {
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#c5a059",
    marginBottom: 12,
  },
  actionCard: {
    padding: 16,
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#c5a059",
    paddingRight: 12,
  },
  actionContent: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  actionIcon: {
    fontSize: 32,
    marginRight: 12,
  },
  actionText: {
    flex: 1,
  },
  actionTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#fff",
    marginBottom: 2,
  },
  actionDescription: {
    fontSize: 12,
    color: "#888",
  },
  featureGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  featureCard: {
    width: "48%",
    backgroundColor: "#1a1a1a",
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#c5a059",
    alignItems: "center",
  },
  featureIcon: {
    fontSize: 28,
    marginBottom: 8,
  },
  featureTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: "#c5a059",
    marginBottom: 4,
  },
  featureDescription: {
    fontSize: 11,
    color: "#888",
    textAlign: "center",
  },
  infoBox: {
    backgroundColor: "#1a1a1a",
    borderWidth: 1,
    borderColor: "#c5a059",
    borderRadius: 12,
    padding: 16,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#c5a059",
    marginBottom: 12,
  },
  infoDetail: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#0a0a0a",
  },
  infoLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: "#888",
  },
  infoValue: {
    fontSize: 12,
    color: "#c5a059",
    fontWeight: "500",
  },
});
