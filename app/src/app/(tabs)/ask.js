import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Header } from '../../components/ui';
import { answerQuestion, SUGGESTED_QUESTIONS } from '../../data/mock';
import { colors } from '../../theme';

const WELCOME = {
  id: 'welcome',
  from: 'bot',
  text: "Hi! Ask me about your mint. I answer only from the pot's sensor data.",
  facts: [],
};

export default function AskScreen() {
  const insets = useSafeAreaInsets();
  const { q, decision } = useLocalSearchParams(); // set when opened from the Decision log
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef(null);

  const send = (text, decisionT) => {
    const question = text.trim();
    if (!question || thinking) return;
    setInput('');
    setMessages((m) => [...m, { id: `u${Date.now()}`, from: 'me', text: question }]);
    setThinking(true);
    const started = Date.now();
    // Offline answers are instant; the delay stands in for the server round trip.
    setTimeout(() => {
      const answer = answerQuestion(question, decisionT);
      setMessages((m) => [
        ...m,
        { id: `b${Date.now()}`, from: 'bot', ...answer, latencyMs: Date.now() - started, rating: null },
      ]);
      setThinking(false);
    }, 600);
  };

  useEffect(() => {
    if (q) {
      send(String(q), decision);
      router.setParams({ q: undefined, decision: undefined });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, decision]);

  const rate = (id, value) =>
    setMessages((m) => m.map((msg) => (msg.id === id ? { ...msg, rating: msg.rating === value ? null : value } : msg)));

  return (
    <KeyboardAvoidingView behavior="padding" style={styles.screen}>
      <View style={[styles.top, { paddingTop: insets.top + 12 }]}>
        <Header title="Ask Nabta" subtitle="Answers from your pot's data" />
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.flex}
        contentContainerStyle={styles.messages}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
        keyboardShouldPersistTaps="handled"
      >
        {messages.map((m) =>
          m.from === 'me' ? (
            <View key={m.id} style={[styles.bubble, styles.me]}>
              <Text style={styles.meText}>{m.text}</Text>
            </View>
          ) : (
            <BotMessage key={m.id} message={m} onRate={rate} />
          )
        )}
        {thinking && (
          <View style={[styles.bubble, styles.bot]}>
            <Text style={styles.meta}>Thinking…</Text>
          </View>
        )}
      </ScrollView>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.suggestions}
        contentContainerStyle={styles.suggestionsRow}
        keyboardShouldPersistTaps="handled"
      >
        {SUGGESTED_QUESTIONS.map((s) => (
          <Pressable key={s} onPress={() => send(s)} style={styles.suggestion}>
            <Text style={styles.suggestionText}>{s}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <View style={styles.inputRow}>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Ask about your plant…"
          placeholderTextColor={colors.muted}
          style={styles.input}
          returnKeyType="send"
          onSubmitEditing={() => send(input)}
        />
        <Pressable
          onPress={() => send(input)}
          disabled={!input.trim()}
          style={[styles.send, !input.trim() && { opacity: 0.4 }]}
          accessibilityRole="button"
          accessibilityLabel="Send"
        >
          <Ionicons name="send" size={18} color={colors.surface} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

function BotMessage({ message, onRate }) {
  const [showFacts, setShowFacts] = useState(false);
  const isWelcome = message.id === 'welcome';

  return (
    <View style={[styles.bubble, styles.bot]}>
      <Text style={styles.botText}>{message.text}</Text>
      {!isWelcome && (
        <>
          {showFacts && (
            <View style={styles.facts}>
              {message.facts.map((f) => (
                <Text key={f} style={styles.fact}>
                  {f}
                </Text>
              ))}
            </View>
          )}
          <View style={styles.botFooter}>
            {message.facts.length > 0 && (
              <Pressable onPress={() => setShowFacts(!showFacts)} hitSlop={8}>
                <Text style={styles.link}>{showFacts ? 'Hide facts' : 'Facts used'}</Text>
              </Pressable>
            )}
            <View style={styles.flex} />
            <Pressable onPress={() => onRate(message.id, 'up')} hitSlop={8} accessibilityLabel="Helpful answer">
              <Ionicons
                name={message.rating === 'up' ? 'thumbs-up' : 'thumbs-up-outline'}
                size={17}
                color={message.rating === 'up' ? colors.leaf : colors.muted}
              />
            </Pressable>
            <Pressable onPress={() => onRate(message.id, 'down')} hitSlop={8} accessibilityLabel="Wrong answer">
              <Ionicons
                name={message.rating === 'down' ? 'thumbs-down' : 'thumbs-down-outline'}
                size={17}
                color={message.rating === 'down' ? colors.crit : colors.muted}
              />
            </Pressable>
          </View>
          <Text style={styles.meta}>
            {message.provider} · {message.model} · {message.latencyMs} ms
          </Text>
        </>
      )}
    </View>
  );
}

const mono = Platform.select({ ios: 'Menlo', default: 'monospace' });

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  top: { paddingHorizontal: 16, paddingBottom: 8 },
  messages: { paddingHorizontal: 16, paddingVertical: 8, gap: 10 },
  bubble: { maxWidth: '85%', borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10, gap: 8 },
  me: { alignSelf: 'flex-end', backgroundColor: colors.water, borderBottomRightRadius: 4 },
  meText: { color: colors.surface, fontSize: 15 },
  bot: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderBottomLeftRadius: 4,
  },
  botText: { color: colors.fg, fontSize: 15, lineHeight: 21 },
  botFooter: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  link: { color: colors.water, fontSize: 13, fontWeight: '600' },
  facts: { backgroundColor: colors.bg, borderRadius: 8, padding: 8, gap: 2 },
  fact: { fontFamily: mono, fontSize: 12, color: colors.muted },
  meta: { fontSize: 11, color: colors.muted },
  suggestions: { flexGrow: 0 },
  suggestionsRow: { paddingHorizontal: 16, paddingVertical: 6, gap: 8 },
  suggestion: {
    borderRadius: 99,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  suggestionText: { fontSize: 13, color: colors.fg },
  inputRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingTop: 6, paddingBottom: 12 },
  input: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 99,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    color: colors.fg,
  },
  send: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.leaf,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
