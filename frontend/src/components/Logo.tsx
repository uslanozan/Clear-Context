import markUrl from '../assets/mark-c.png';

// The Clear Context mark: a broken glass C. A raster on purpose: the glass edges do not survive vectorizing.
interface Props {
  size?: number;
}

export function LogoMark({ size = 28 }: Props) {
  return (
    <img src={markUrl} width={size} height={size} alt="" style={{ borderRadius: size * 0.22 }} />
  );
}
