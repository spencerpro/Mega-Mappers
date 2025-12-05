
import pygame

def calculate_catmull_rom(points, resolution=10):
    """
    Generates a list of points representing a smooth Catmull-Rom spline 
    passing through the given control points.
    """
    if len(points) < 2:
        return points

    # Duplicate start and end points to ensure the curve goes through them
    # Catmull-Rom requires 4 points (p0, p1, p2, p3) to draw segment p1->p2
    pts = [points[0]] + points + [points[-1]]
    
    curve_points = []

    for i in range(len(pts) - 3):
        p0 = pts[i]
        p1 = pts[i + 1]
        p2 = pts[i + 2]
        p3 = pts[i + 3]

        for t_step in range(resolution):
            t = t_step / resolution
            t2 = t * t
            t3 = t2 * t

            # Catmull-Rom Matrix calculation
            x = 0.5 * ((2 * p1[0]) +
                       (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            
            y = 0.5 * ((2 * p1[1]) +
                       (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            
            curve_points.append((x, y))

    # Add the very last point
    curve_points.append(points[-1])
    return curve_points
