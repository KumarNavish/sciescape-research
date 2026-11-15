// A perspective view of an existing equirectangular image, not generated geometry.
// Apache-2.0. Draws only after input, image loading, or a resize.
export function createPanorama(canvas, { onError = () => {}, onViewChange = () => {} } = {}) {
  const gl = canvas.getContext('webgl', {
    alpha: false, antialias: false, depth: false, stencil: false,
    preserveDrawingBuffer: false, powerPreference: 'low-power',
  });
  if (!gl) throw new Error('This browser cannot display the interactive panorama.');

  let destroyed = false;
  let lost = false;
  let frame = 0;
  let texture = null;
  let pending = null;
  let dragging = null;
  let view = { yaw: 0, pitch: 0, fov: 75 };
  let initialView = { ...view };
  const radians = Math.PI / 180;
  const shaders = [];
  let program;
  let vertices;
  const abortError = () => new DOMException('Panorama loading was cancelled.', 'AbortError');
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function shader(type, source) {
    const compiled = gl.createShader(type);
    if (!compiled) throw new Error('The panorama renderer could not start.');
    shaders.push(compiled);
    gl.shaderSource(compiled, source);
    gl.compileShader(compiled);
    if (!gl.getShaderParameter(compiled, gl.COMPILE_STATUS)) {
      throw new Error('The panorama renderer is not supported on this device.');
    }
    return compiled;
  }

  try {
    program = gl.createProgram();
    if (!program) throw new Error('The panorama renderer could not start.');
    const precision = gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER, gl.HIGH_FLOAT).precision ? 'highp' : 'mediump';
    gl.attachShader(program, shader(gl.VERTEX_SHADER, `
      attribute vec2 position;
      varying vec2 screenPosition;
      void main() {
        screenPosition = position;
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `
      precision ${precision} float;
      varying vec2 screenPosition;
      uniform sampler2D panorama;
      uniform float aspect;
      uniform float scale;
      uniform vec2 angle;
      void main() {
        vec3 ray = normalize(vec3(screenPosition.x * aspect * scale, screenPosition.y * scale, 1.0));
        float cp = cos(angle.y), sp = sin(angle.y);
        ray = vec3(ray.x, cp * ray.y + sp * ray.z, -sp * ray.y + cp * ray.z);
        float cy = cos(angle.x), sy = sin(angle.x);
        ray = vec3(cy * ray.x + sy * ray.z, ray.y, -sy * ray.x + cy * ray.z);
        vec2 uv = vec2(fract(atan(ray.x, ray.z) / 6.28318530718 + 0.5), asin(clamp(ray.y, -1.0, 1.0)) / 3.14159265359 + 0.5);
        gl_FragColor = texture2D(panorama, uv);
      }
    `));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('The panorama renderer could not start.');
    gl.useProgram(program);
    vertices = gl.createBuffer();
    if (!vertices) throw new Error('The panorama renderer could not start.');
    gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    gl.uniform1i(gl.getUniformLocation(program, 'panorama'), 0);
  } catch (error) {
    if (vertices) gl.deleteBuffer(vertices);
    if (program) gl.deleteProgram(program);
    shaders.forEach((item) => gl.deleteShader(item));
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    throw error;
  }

  const uniforms = Object.fromEntries(['aspect', 'scale', 'angle'].map((key) => [key, gl.getUniformLocation(program, key)]));
  const maxSize = gl.getParameter(gl.MAX_RENDERBUFFER_SIZE);
  const maxTexture = gl.getParameter(gl.MAX_TEXTURE_SIZE);

  function draw() {
    frame = 0;
    if (destroyed || lost || !texture || document.hidden) return;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(2000000 / (width * height)), maxSize / width, maxSize / height);
    const pixelWidth = Math.max(1, Math.floor(width * ratio));
    const pixelHeight = Math.max(1, Math.floor(height * ratio));
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    gl.viewport(0, 0, pixelWidth, pixelHeight);
    gl.uniform1f(uniforms.aspect, width / height);
    gl.uniform1f(uniforms.scale, Math.tan(view.fov * radians / 2));
    gl.uniform2f(uniforms.angle, view.yaw * radians, view.pitch * radians);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  function schedule() {
    if (!destroyed && !lost && !document.hidden && !frame) frame = requestAnimationFrame(draw);
  }

  function setView(next) {
    if (destroyed || lost) return;
    const yaw = Number.isFinite(next.yaw) ? next.yaw : view.yaw;
    view = {
      yaw: ((yaw + 180) % 360 + 360) % 360 - 180,
      pitch: clamp(Number.isFinite(next.pitch) ? next.pitch : view.pitch, -85, 85),
      fov: clamp(Number.isFinite(next.fov) ? next.fov : view.fov, 40, 100),
    };
    onViewChange({ ...view });
    schedule();
  }

  function cancelLoad() {
    if (!pending) return;
    const old = pending;
    pending = null;
    old.image.onload = old.image.onerror = null;
    old.image.removeAttribute('src');
    old.reject(abortError());
  }

  function load(src, options = {}) {
    if (destroyed || lost) return Promise.reject(new Error('The panorama renderer is no longer available.'));
    cancelLoad();
    return new Promise((resolve, reject) => {
      const image = new Image();
      const request = { image, reject };
      pending = request;
      image.decoding = 'async';
      image.crossOrigin = 'anonymous';
      const fail = (error) => {
        if (pending !== request) return;
        pending = null;
        image.onload = image.onerror = null;
        reject(error);
        onError(error);
      };
      image.onerror = () => fail(new Error('This panorama could not be loaded.'));
      image.onload = () => {
        if (destroyed || lost || pending !== request) return;
        let replacement;
        try {
          if (image.naturalWidth > maxTexture || image.naturalHeight > maxTexture) throw new Error('This panorama exceeds the image limit of this device.');
          replacement = gl.createTexture();
          if (!replacement) throw new Error('There is not enough graphics memory to open this panorama.');
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, replacement);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
          if (gl.getError() !== gl.NO_ERROR) throw new Error('This device could not display the panorama.');
          if (texture) gl.deleteTexture(texture);
          texture = replacement;
          pending = null;
          image.onload = image.onerror = null;
          initialView = { yaw: options.yaw ?? 0, pitch: options.pitch ?? 0, fov: options.fov ?? 75 };
          setView(initialView);
          // Upload first; draw now if visible, otherwise on visibility restoration.
          if (frame) cancelAnimationFrame(frame);
          draw();
          resolve();
        } catch (error) {
          if (replacement) gl.deleteTexture(replacement);
          if (texture) gl.bindTexture(gl.TEXTURE_2D, texture);
          fail(error);
        }
      };
      image.src = src;
    });
  }

  function pointerDown(event) {
    if (!event.isPrimary || event.button !== 0 || destroyed || lost) return;
    dragging = { id: event.pointerId, x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
    canvas.focus({ preventScroll: true });
    canvas.classList.add('is-dragging');
  }
  function pointerMove(event) {
    if (!dragging || dragging.id !== event.pointerId) return;
    const degreesPerPixel = view.fov / Math.max(canvas.clientHeight, 1);
    setView({ yaw: view.yaw - (event.clientX - dragging.x) * degreesPerPixel, pitch: view.pitch + (event.clientY - dragging.y) * degreesPerPixel });
    dragging.x = event.clientX;
    dragging.y = event.clientY;
  }
  function pointerEnd(event) {
    if (!dragging || (event && event.pointerId !== dragging.id)) return;
    const id = dragging.id;
    dragging = null;
    canvas.classList.remove('is-dragging');
    if (canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id);
  }
  function keyDown(event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const step = event.shiftKey ? 12 : 4;
    const movements = {
      ArrowLeft: { yaw: view.yaw - step }, ArrowRight: { yaw: view.yaw + step },
      ArrowUp: { pitch: view.pitch + step }, ArrowDown: { pitch: view.pitch - step },
      '+': { fov: view.fov - 5 }, '=': { fov: view.fov - 5 },
      '-': { fov: view.fov + 5 }, _: { fov: view.fov + 5 }, Home: initialView,
    };
    if (!Object.hasOwn(movements, event.key)) return;
    event.preventDefault();
    setView(movements[event.key]);
  }
  function visibilityChange() {
    if (document.hidden) {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      pointerEnd();
    } else schedule();
  }
  function contextLost(event) {
    event.preventDefault();
    if (destroyed) return;
    lost = true;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    pointerEnd();
    cancelLoad();
    onError(new Error('The interactive view was paused by your device. The original image is still available.'));
  }

  const resizeObserver = new ResizeObserver(schedule);
  resizeObserver.observe(canvas);
  canvas.addEventListener('pointerdown', pointerDown);
  canvas.addEventListener('pointermove', pointerMove);
  canvas.addEventListener('pointerup', pointerEnd);
  canvas.addEventListener('pointercancel', pointerEnd);
  canvas.addEventListener('lostpointercapture', pointerEnd);
  canvas.addEventListener('keydown', keyDown);
  canvas.addEventListener('webglcontextlost', contextLost);
  document.addEventListener('visibilitychange', visibilityChange);
  window.addEventListener('resize', schedule);

  return {
    load, setView,
    getView: () => ({ ...view }),
    resize: schedule,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      cancelLoad();
      pointerEnd();
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      resizeObserver.disconnect();
      canvas.removeEventListener('pointerdown', pointerDown);
      canvas.removeEventListener('pointermove', pointerMove);
      canvas.removeEventListener('pointerup', pointerEnd);
      canvas.removeEventListener('pointercancel', pointerEnd);
      canvas.removeEventListener('lostpointercapture', pointerEnd);
      canvas.removeEventListener('keydown', keyDown);
      canvas.removeEventListener('webglcontextlost', contextLost);
      document.removeEventListener('visibilitychange', visibilityChange);
      window.removeEventListener('resize', schedule);
      if (texture) gl.deleteTexture(texture);
      gl.deleteBuffer(vertices);
      gl.deleteProgram(program);
      shaders.forEach((item) => gl.deleteShader(item));
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      texture = null;
    },
  };
}
