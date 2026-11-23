import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import { colors } from '../../theme';

const TABS = [
  { name: 'index', title: 'Home', icon: 'leaf' },
  { name: 'history', title: 'History', icon: 'stats-chart' },
  { name: 'ask', title: 'Ask', icon: 'chatbubble-ellipses' },
  { name: 'log', title: 'Log', icon: 'list' },
  { name: 'check', title: 'Check', icon: 'clipboard' },
];

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarHideOnKeyboard: true,
        tabBarActiveTintColor: colors.leaf,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.line },
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color, size }) => <Ionicons name={tab.icon} size={size} color={color} />,
          }}
        />
      ))}
    </Tabs>
  );
}
