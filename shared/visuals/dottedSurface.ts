export type SurfaceBackgroundTheme = 'light' | 'dark';
export type SurfaceBackgroundStyle = 'dotted' | 'mesh';

export interface SurfaceBackgroundConfig {
  amplitude?: number;
  density?: number;
  opacity?: number;
  speed?: number;
  style?: SurfaceBackgroundStyle;
  theme: SurfaceBackgroundTheme;
}

export interface SurfaceBackgroundControls {
  destroy(): void;
  redraw(time?: number): void;
  resize(): void;
}

const BASE_COLUMNS = 60;
const BASE_ROWS = 60;
const SPREAD = 300;
const FREQUENCY_X = 0.022;
const FREQUENCY_Z = 0.022;
const BASE_SPEED = 0.0009;
const ANGLE = (62 * Math.PI) / 180;
const COS_ANGLE = Math.cos(ANGLE);
const SIN_ANGLE = Math.sin(ANGLE);
const CAMERA_Z = -180;
const CAMERA_Y = 60;
const FOCAL_LENGTH = 420;

interface ResolvedSurfaceBackgroundConfig {
  amplitude: number;
  columns: number;
  density: number;
  opacity: number;
  rows: number;
  speed: number;
  style: SurfaceBackgroundStyle;
  theme: SurfaceBackgroundTheme;
}

interface BackgroundPalette {
  fillAlpha: number;
  fillBase: string;
  horizonAlpha: number;
  horizonTint: string;
  meshIntersectionAlpha: number;
  meshIntersectionBase: string;
  meshStrokeAlpha: number;
  meshStrokeBase: string;
}

interface ProjectedPoint {
  alpha: number;
  depth: number;
  size: number;
  x: number;
  y: number;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function resolveConfig(
  config: SurfaceBackgroundConfig,
): ResolvedSurfaceBackgroundConfig {
  const density = clamp(config.density ?? 1, 0.45, 1.5);

  return {
    amplitude: clamp(config.amplitude ?? 18, 4, 42),
    columns: Math.max(18, Math.round(BASE_COLUMNS * density)),
    density,
    opacity: clamp(config.opacity ?? 1, 0.2, 1.2),
    rows: Math.max(18, Math.round(BASE_ROWS * density)),
    speed: BASE_SPEED * clamp(config.speed ?? 1, 0.35, 2),
    style: config.style ?? 'dotted',
    theme: config.theme,
  };
}

function getPalette(theme: SurfaceBackgroundTheme): BackgroundPalette {
  return theme === 'dark'
    ? {
        fillAlpha: 0.55,
        fillBase: '190, 195, 215',
        horizonAlpha: 0.18,
        horizonTint: '120, 160, 220',
        meshIntersectionAlpha: 0.18,
        meshIntersectionBase: '188, 201, 228',
        meshStrokeAlpha: 0.26,
        meshStrokeBase: '143, 166, 218',
      }
    : {
        fillAlpha: 0.4,
        fillBase: '85, 90, 110',
        horizonAlpha: 0.1,
        horizonTint: '80, 110, 200',
        meshIntersectionAlpha: 0.1,
        meshIntersectionBase: '119, 136, 178',
        meshStrokeAlpha: 0.16,
        meshStrokeBase: '95, 118, 174',
      };
}

function projectSurfacePoints(
  config: ResolvedSurfaceBackgroundConfig,
  time: number,
  width: number,
  height: number,
) {
  const step = (SPREAD * 2) / config.columns;
  const centerX = width / 2;
  const centerY = height / 2;
  const dots: ProjectedPoint[] = [];
  const grid: Array<Array<ProjectedPoint | null>> = Array.from(
    { length: config.rows + 1 },
    () => Array.from({ length: config.columns + 1 }, () => null),
  );

  for (let columnIndex = 0; columnIndex <= config.columns; columnIndex += 1) {
    for (let rowIndex = 0; rowIndex <= config.rows; rowIndex += 1) {
      const worldX = -SPREAD + columnIndex * step;
      const worldZ = -SPREAD + rowIndex * step;
      const wave =
        Math.sin(worldX * FREQUENCY_X + time * config.speed) +
        Math.sin(worldZ * FREQUENCY_Z + time * config.speed * 1.4);
      const worldY = (wave / 2) * config.amplitude;
      const tiltedY = worldY * COS_ANGLE - worldZ * SIN_ANGLE;
      const tiltedZ = worldY * SIN_ANGLE + worldZ * COS_ANGLE - CAMERA_Z;

      if (tiltedZ <= 1) {
        continue;
      }

      const screenX = (worldX / tiltedZ) * FOCAL_LENGTH + centerX;
      const screenY = ((tiltedY - CAMERA_Y) / tiltedZ) * FOCAL_LENGTH + centerY;
      const size = (FOCAL_LENGTH / tiltedZ) * 1.2;

      if (size < 0.32) {
        continue;
      }

      const fog = Math.max(0, Math.min(1, 1 - (tiltedZ - 100) / 400));
      const alpha = fog * config.opacity;

      if (alpha < 0.015) {
        continue;
      }

      const point = {
        alpha,
        depth: tiltedZ,
        size,
        x: screenX,
        y: screenY,
      };

      dots.push(point);

      const projectedRow = grid[rowIndex];

      if (projectedRow) {
        projectedRow[columnIndex] = point;
      }
    }
  }

  return { dots, grid };
}

function drawGradient(
  context: CanvasRenderingContext2D,
  palette: BackgroundPalette,
  config: ResolvedSurfaceBackgroundConfig,
  width: number,
  height: number,
) {
  const centerX = width / 2;
  const centerY = height / 2;
  const gradient = context.createRadialGradient(
    centerX,
    centerY * 0.65,
    0,
    centerX,
    centerY * 0.65,
    Math.max(width, height) * 0.55,
  );

  gradient.addColorStop(
    0,
    `rgba(${palette.horizonTint}, ${(palette.horizonAlpha * config.opacity).toFixed(3)})`,
  );
  gradient.addColorStop(1, `rgba(${palette.horizonTint}, 0)`);
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);
}

function drawDottedSurface(
  context: CanvasRenderingContext2D,
  palette: BackgroundPalette,
  dots: ProjectedPoint[],
) {
  dots.sort((left, right) => right.depth - left.depth);

  for (const dot of dots) {
    context.beginPath();
    context.arc(dot.x, dot.y, dot.size, 0, Math.PI * 2);
    context.fillStyle = `rgba(${palette.fillBase}, ${(palette.fillAlpha * dot.alpha).toFixed(3)})`;
    context.fill();
  }
}

function drawMeshSurface(
  context: CanvasRenderingContext2D,
  palette: BackgroundPalette,
  grid: Array<Array<ProjectedPoint | null>>,
) {
  const drawSegment = (
    start: ProjectedPoint,
    end: ProjectedPoint,
    alphaScale: number,
  ) => {
    const alpha =
      ((start.alpha + end.alpha) / 2) * palette.meshStrokeAlpha * alphaScale;

    if (alpha < 0.02) {
      return;
    }

    const lineWidth = Math.max(0.35, ((start.size + end.size) / 2) * 0.32);
    context.beginPath();
    context.moveTo(start.x, start.y);
    context.lineTo(end.x, end.y);
    context.lineWidth = lineWidth;
    context.strokeStyle = `rgba(${palette.meshStrokeBase}, ${alpha.toFixed(3)})`;
    context.stroke();
  };

  context.lineCap = 'round';
  context.lineJoin = 'round';

  for (const row of grid) {
    for (let columnIndex = 1; columnIndex < row.length; columnIndex += 1) {
      const start = row[columnIndex - 1];
      const end = row[columnIndex];

      if (start && end) {
        drawSegment(start, end, 1);
      }
    }
  }

  for (
    let columnIndex = 0;
    columnIndex < (grid[0]?.length ?? 0);
    columnIndex += 1
  ) {
    for (let rowIndex = 1; rowIndex < grid.length; rowIndex += 1) {
      const start = grid[rowIndex - 1]?.[columnIndex];
      const end = grid[rowIndex]?.[columnIndex];

      if (start && end) {
        drawSegment(start, end, 0.72);
      }
    }
  }

  for (let rowIndex = 0; rowIndex < grid.length; rowIndex += 2) {
    for (
      let columnIndex = 0;
      columnIndex < (grid[rowIndex]?.length ?? 0);
      columnIndex += 2
    ) {
      const point = grid[rowIndex]?.[columnIndex];

      if (!point) {
        continue;
      }

      const alpha = point.alpha * palette.meshIntersectionAlpha;

      if (alpha < 0.025) {
        continue;
      }

      context.beginPath();
      context.arc(
        point.x,
        point.y,
        Math.max(0.35, point.size * 0.38),
        0,
        Math.PI * 2,
      );
      context.fillStyle = `rgba(${palette.meshIntersectionBase}, ${alpha.toFixed(3)})`;
      context.fill();
    }
  }
}

export function mountSurfaceBackground(
  canvas: HTMLCanvasElement,
  getConfig: () => SurfaceBackgroundConfig,
): SurfaceBackgroundControls {
  if (typeof window === 'undefined') {
    return {
      destroy() {},
      redraw() {},
      resize() {},
    };
  }

  const context = canvas.getContext('2d');

  if (!context) {
    return {
      destroy() {},
      redraw() {},
      resize() {},
    };
  }

  const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let prefersReducedMotion = motionQuery?.matches ?? false;
  let animationFrameId = 0;
  let width = 0;
  let height = 0;

  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    const devicePixelRatio = window.devicePixelRatio || 1;

    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    canvas.width = Math.floor(width * devicePixelRatio);
    canvas.height = Math.floor(height * devicePixelRatio);
    context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  };

  const drawFrame = (time: number) => {
    const config = resolveConfig(getConfig());
    const palette = getPalette(config.theme);

    context.clearRect(0, 0, width, height);
    drawGradient(context, palette, config, width, height);

    const { dots, grid } = projectSurfacePoints(config, time, width, height);

    if (config.style === 'mesh') {
      drawMeshSurface(context, palette, grid);
      return;
    }

    drawDottedSurface(context, palette, dots);
  };

  const stopAnimation = () => {
    window.cancelAnimationFrame(animationFrameId);
    animationFrameId = 0;
  };

  const tick = (time: number) => {
    drawFrame(time);

    if (!prefersReducedMotion && !document.hidden) {
      animationFrameId = window.requestAnimationFrame(tick);
    }
  };

  const startAnimation = () => {
    stopAnimation();

    if (prefersReducedMotion || document.hidden) {
      drawFrame(0);
      return;
    }

    animationFrameId = window.requestAnimationFrame(tick);
  };

  const handleVisibilityChange = () => {
    startAnimation();
  };

  const handleMotionChange = (event: MediaQueryListEvent) => {
    prefersReducedMotion = event.matches;
    startAnimation();
  };

  resize();
  startAnimation();

  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  motionQuery?.addEventListener?.('change', handleMotionChange);

  return {
    destroy() {
      stopAnimation();
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      motionQuery?.removeEventListener?.('change', handleMotionChange);
    },
    redraw(time = 0) {
      drawFrame(time);
    },
    resize,
  };
}

export function mountDottedSurface(
  canvas: HTMLCanvasElement,
  getConfig: () => Omit<SurfaceBackgroundConfig, 'style'>,
) {
  return mountSurfaceBackground(canvas, () => ({
    ...getConfig(),
    style: 'dotted',
  }));
}
