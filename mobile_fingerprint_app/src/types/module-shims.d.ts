declare module "expo-linear-gradient" {
  export const LinearGradient: any;
}

declare module "expo-secure-store" {
  export function setItemAsync(key: string, value: string): Promise<void>;
  export function getItemAsync(key: string): Promise<string | null>;
  export function deleteItemAsync(key: string): Promise<void>;
}

declare module "@react-navigation/native" {
  export const NavigationContainer: any;
  export function useNavigation<T = any>(): T;
}

declare module "@react-navigation/native-stack" {
  export function createNativeStackNavigator(): any;
}

declare module "@react-navigation/bottom-tabs" {
  export function createBottomTabNavigator(): any;
}
