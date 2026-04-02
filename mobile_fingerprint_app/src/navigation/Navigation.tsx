import React from "react";
import { Text } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { HomeScreen } from "../screens/HomeScreen";
import { EnrollmentScreen } from "../screens/EnrollmentScreen";
import { AuthenticationScreen } from "../screens/AuthenticationScreen";

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const EnrollmentStack = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        animationEnabled: true,
      }}
    >
      <Stack.Screen name="EnrollmentHome" component={EnrollmentScreen} />
    </Stack.Navigator>
  );
};

const AuthenticationStack = () => {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        animationEnabled: true,
      }}
    >
      <Stack.Screen
        name="AuthenticationHome"
        component={AuthenticationScreen}
      />
    </Stack.Navigator>
  );
};

export const RootNavigator = () => {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: "#c5a059",
          tabBarInactiveTintColor: "#666",
          tabBarStyle: {
            backgroundColor: "#1a1a1a",
            borderTopColor: "#c5a059",
            borderTopWidth: 0.5,
            height: 60,
            paddingBottom: 8,
          },
        }}
      >
        <Tab.Screen
          name="Home"
          component={HomeScreen}
          options={{
            tabBarLabel: "Home",
            tabBarIcon: ({ color }: { color: string }) => (
              <Text style={{ fontSize: 20, color }}>🏠</Text>
            ),
          }}
        />
        <Tab.Screen
          name="Enroll"
          component={EnrollmentStack}
          options={{
            tabBarLabel: "Enroll",
            tabBarIcon: ({ color }: { color: string }) => (
              <Text style={{ fontSize: 20, color }}>📋</Text>
            ),
          }}
        />
        <Tab.Screen
          name="Auth"
          component={AuthenticationStack}
          options={{
            tabBarLabel: "Authenticate",
            tabBarIcon: ({ color }: { color: string }) => (
              <Text style={{ fontSize: 20, color }}>🔐</Text>
            ),
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
};
