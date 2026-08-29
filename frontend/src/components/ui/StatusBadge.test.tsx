import { render, screen } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import { describe, expect, it } from 'vitest';

import { StatusBadge } from './StatusBadge';
import theme from '../../theme';

describe('StatusBadge', () => {
  it('renders the status label', () => {
    render(
      <ChakraProvider theme={theme}>
        <StatusBadge status="ready" />
      </ChakraProvider>,
    );

    expect(screen.getByText('ready')).toBeInTheDocument();
  });
});
