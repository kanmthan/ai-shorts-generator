import {
  extendTheme,
  type StyleFunctionProps,
  type ThemeConfig,
} from '@chakra-ui/react';

export const colorModeConfig: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

const fontStack =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

const theme = extendTheme({
  config: colorModeConfig,
  colors: {
    brand: {
      50: '#eef2ff',
      100: '#e0e7ff',
      200: '#c7d2fe',
      300: '#a5b4fc',
      400: '#818cf8',
      500: '#6366f1',
      600: '#4f46e5',
      700: '#4338ca',
      800: '#3730a3',
      900: '#312e81',
    },
  },
  fonts: {
    heading: fontStack,
    body: fontStack,
  },
  styles: {
    global: (props: StyleFunctionProps) => ({
      body: {
        bg: props.colorMode === 'dark' ? 'gray.900' : 'gray.50',
        color: props.colorMode === 'dark' ? 'gray.100' : 'gray.800',
      },
    }),
  },
  components: {
    Button: {
      baseStyle: { borderRadius: 'lg', fontWeight: 'semibold' },
    },
  },
});

export default theme;
