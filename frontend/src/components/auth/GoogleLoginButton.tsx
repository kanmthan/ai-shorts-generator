import { Button, type ButtonProps } from '@chakra-ui/react';

import { startGoogleLogin } from '../../services/authService';

type GoogleLoginButtonProps = Omit<ButtonProps, 'onClick' | 'children'> & {
  label?: string;
};

/** Full-width outline button that hands off to the backend Google OAuth flow. */
export function GoogleLoginButton({
  label = 'Continue with Google',
  ...rest
}: GoogleLoginButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      width="full"
      fontWeight="medium"
      onClick={startGoogleLogin}
      {...rest}
    >
      {label}
    </Button>
  );
}
