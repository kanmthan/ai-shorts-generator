/**
 * Per-browser default editing preferences, persisted to localStorage.
 * All storage access is wrapped in try/catch so a disabled/full store never
 * breaks the settings page.
 */
import { useEffect, useState } from 'react';
import {
  FormControl,
  FormLabel,
  Heading,
  Select,
  Stack,
  Switch,
  useToast,
} from '@chakra-ui/react';

import { GlassCard, GradientButton } from '../ui';

const STORAGE_KEY = 'ase.editingPrefs';

const CAPTION_STYLES = ['minimal', 'bold', 'karaoke', 'word_by_word'] as const;
type CaptionStyle = (typeof CAPTION_STYLES)[number];

export interface EditingPrefs {
  captionStyle: CaptionStyle;
  addZoom: boolean;
  backgroundMusic: boolean;
}

const DEFAULT_PREFS: EditingPrefs = {
  captionStyle: 'bold',
  addZoom: true,
  backgroundMusic: false,
};

function isCaptionStyle(value: unknown): value is CaptionStyle {
  return (
    typeof value === 'string' &&
    (CAPTION_STYLES as ReadonlyArray<string>).includes(value)
  );
}

function loadPrefs(): EditingPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFS;
    }
    const parsed = JSON.parse(raw) as Partial<Record<keyof EditingPrefs, unknown>>;
    return {
      captionStyle: isCaptionStyle(parsed.captionStyle)
        ? parsed.captionStyle
        : DEFAULT_PREFS.captionStyle,
      addZoom:
        typeof parsed.addZoom === 'boolean'
          ? parsed.addZoom
          : DEFAULT_PREFS.addZoom,
      backgroundMusic:
        typeof parsed.backgroundMusic === 'boolean'
          ? parsed.backgroundMusic
          : DEFAULT_PREFS.backgroundMusic,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

function savePrefs(prefs: EditingPrefs): boolean {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    return true;
  } catch {
    return false;
  }
}

const CAPTION_STYLE_LABELS: Record<CaptionStyle, string> = {
  minimal: 'Minimal',
  bold: 'Bold',
  karaoke: 'Karaoke',
  word_by_word: 'Word by word',
};

export function DefaultEditingPrefs() {
  const toast = useToast();
  const [prefs, setPrefs] = useState<EditingPrefs>(DEFAULT_PREFS);

  useEffect(() => {
    setPrefs(loadPrefs());
  }, []);

  const handleSave = (): void => {
    const ok = savePrefs(prefs);
    toast({
      title: ok ? 'Preferences saved' : 'Could not save preferences',
      status: ok ? 'success' : 'error',
      duration: 4000,
      isClosable: true,
    });
  };

  return (
    <GlassCard interactive={false}>
      <Stack spacing={5}>
        <Heading size="md">Default editing preferences</Heading>

        <FormControl>
          <FormLabel>Caption style</FormLabel>
          <Select
            value={prefs.captionStyle}
            onChange={(event) =>
              setPrefs((prev) => ({
                ...prev,
                captionStyle: isCaptionStyle(event.target.value)
                  ? event.target.value
                  : prev.captionStyle,
              }))
            }
          >
            {CAPTION_STYLES.map((style) => (
              <option key={style} value={style}>
                {CAPTION_STYLE_LABELS[style]}
              </option>
            ))}
          </Select>
        </FormControl>

        <FormControl
          display="flex"
          alignItems="center"
          justifyContent="space-between"
        >
          <FormLabel htmlFor="prefs-add-zoom" mb={0}>
            Add zoom effects
          </FormLabel>
          <Switch
            id="prefs-add-zoom"
            isChecked={prefs.addZoom}
            onChange={(event) =>
              setPrefs((prev) => ({ ...prev, addZoom: event.target.checked }))
            }
          />
        </FormControl>

        <FormControl
          display="flex"
          alignItems="center"
          justifyContent="space-between"
        >
          <FormLabel htmlFor="prefs-bg-music" mb={0}>
            Background music
          </FormLabel>
          <Switch
            id="prefs-bg-music"
            isChecked={prefs.backgroundMusic}
            onChange={(event) =>
              setPrefs((prev) => ({
                ...prev,
                backgroundMusic: event.target.checked,
              }))
            }
          />
        </FormControl>

        <GradientButton onClick={handleSave} alignSelf="flex-start" size="sm">
          Save preferences
        </GradientButton>
      </Stack>
    </GlassCard>
  );
}
