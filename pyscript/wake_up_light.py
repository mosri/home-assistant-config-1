"""Emulates a Philips Wake-up Light / sunrise.

This cycles through a sequence of RGB tuples and then
linearily interpolates them in HSV color space as time
proceeds.

The routine can be triggered by toggling an input_boolean.

The sequence is canceled by turning the light on and off.

# Example `configuration.yaml`:
```
input_boolean:
  wake_up_light:
    name: Start wake up light
    initial: off
    icon: mdi:weather-sunset-up
```
"""

import bisect
import colorsys

DEFAULT_LAMP = "light.ceiling_bedroom"
DEFAULT_TOTAL_TIME = 900
DEFAULT_INPUT_BOOLEAN = "input_boolean.wake_up_light"

DEFAULTS = {
    "lamp": DEFAULT_LAMP,
    "total_time": DEFAULT_TOTAL_TIME,
    "input_boolean": DEFAULT_INPUT_BOOLEAN,
}

RGB_SEQUENCE = [
    (255, 0, 0),
    (255, 0, 0),
    (255, 63, 0),
    (255, 120, 0),
    (255, 187, 131),
    (255, 205, 166),
]

MIN_TIME_STEP = 2  # time between settings


def interpolate(xs, ys):
    if any(y - x <= 0 for x, y in zip(xs, xs[1:])):
        raise ValueError("xs must be in strictly ascending order!")
    assert len(xs) == len(ys)
    intervals = zip(xs, xs[1:], ys, ys[1:])
    slopes = [(y2 - y1) / (x2 - x1) for x1, x2, y1, y2 in intervals]

    def _wrapped(self, x):
        if not (xs[0] <= x <= xs[-1]):
            raise ValueError("x out of bounds!")
        if x == xs[-1]:
            return ys[-1]
        i = bisect.bisect_right(xs, x) - 1
        return ys[i] + slopes[i] * (x - xs[i])

    return _wrapped


def linspace(a, b, n=100):
    if n < 2:
        return b
    diff = (float(b) - a) / (n - 1)
    return [diff * i + a for i in range(n)]


def ensure_list(x):
    if isinstance(x, list):
        return x
    return [x]


def rgb_and_brightness(total_time, rgb_sequence):
    """Return interpolator objects for `rgb` and `brightness`.

    This interpolates in the HSV domain and converts it back to RGB.

    Parameters
    ----------
    total_time : int
        Total time.
    rgb_sequence : list of (r, g, b) tuples
        List with tuples of RGB values, where the values are integers.

    Returns
    -------
    rgb : callable
        Interpolation object that returns RGB values as function of time.
    brightness : callable
        Interpolation object that returns brightness values as function of time.
    """
    xs = linspace(0, total_time, len(rgb_sequence))
    hsvs = zip(*[colorsys.rgb_to_hsv(*rgb) for rgb in rgb_sequence])
    hue, saturation, value = [interpolate(xs, ys) for ys in hsvs]
    # start at brightness=2 because it considers 1 to be off...
    _brightness = interpolate([0, total_time], [2, 255])

    def rgb(t):
        rgb = colorsys.hsv_to_rgb(hue(t), saturation(t), value(t))
        return tuple(round(x) for x in rgb)

    def brightness(t):
        return round(_brightness(t))

    return rgb, brightness


@service
def wake_up_light(
    lamp=DEFAULT_LAMP,
    total_time=DEFAULT_TOTAL_TIME,
    input_boolean=DEFAULT_INPUT_BOOLEAN,
):
    service.call("input_boolean", "turn_off", entity_id=input_boolean)
    rgb, brightness = rgb_and_brightness(total_time, RGB_SEQUENCE)
    steps = min(total_time // MIN_TIME_STEP, 255) + 1
    transition = total_time / (steps - 1)
    t = 0
    for i in range(steps):
        service.call(
            *lamp.split("."),
            entity_id=lamp,
            rgb_color=rgb(t),
            brightness=brightness(t),
            transition=transition,
        )
        task.sleep(transition)
        t += transition
