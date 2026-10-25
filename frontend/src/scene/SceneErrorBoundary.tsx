import { Component, type ReactNode } from 'react';

interface Props {
  fallback: ReactNode;
  children: ReactNode;
}

export default class SceneErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.warn('3D scene failed, showing the 2D plan', error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
