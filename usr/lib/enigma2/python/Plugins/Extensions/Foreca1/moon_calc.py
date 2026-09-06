#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# moon_calc.py - Accurate lunar calculations based on Meeus algorithms
# Converted from numpy to pure math for Enigma2 compatibility

import math


# ----------------------------------------------------------------------
# Helper: Normalize angles to degrees (0-360)
def _deg_norm(x):
    x = x % 360.0
    if x < 0:
        x += 360.0
    return x


# ----------------------------------------------------------------------
# Coordinate conversion: Ecliptic -> Equatorial
def EKLtoEKU(_lambda, _beta, _epsilon=23.439607):
    sin_beta = math.sin(math.radians(_beta))
    cos_beta = math.cos(math.radians(_beta))
    sin_lambda = math.sin(math.radians(_lambda))
    cos_lambda = math.cos(math.radians(_lambda))
    cos_eps = math.cos(math.radians(_epsilon))
    sin_eps = math.sin(math.radians(_epsilon))

    _delta = math.degrees(
        math.asin(
            sin_beta * cos_eps + sin_lambda * cos_beta * sin_eps))
    _delta = _deg_norm(_delta)

    _alpha = math.degrees(math.atan2(
        sin_lambda * cos_eps - math.tan(math.radians(_beta)) * sin_eps, cos_lambda))
    _alpha = _deg_norm(_alpha)
    return _alpha, _delta


# ----------------------------------------------------------------------
# Julian Day from Gregorian date
def DtoJD(D, M, Y, hrs=0, mnt=0, dtk=0):
    A = Y // 100
    B = 2 - A + A // 4
    # Julian calendar correction
    if Y < 1582:
        B = 0
    elif Y == 1582:
        if M < 10:
            B = 0
        elif M > 10:
            B = B
        elif M == 10:
            if D < 5:
                B = 0
            elif D > 14:
                B = B
            else:
                raise ValueError("Date not found in Gregorian transition")
    if 0 < M <= 2:
        Y -= 1
        M += 12
    JD = 1720994.5 + int(365.25 * Y) + int(30.60001 * (M + 1)) + D + B
    JD += hrs / 24.0 + mnt / (24.0 * 60.0) + dtk / (24.0 * 3600.0)
    return JD


# ----------------------------------------------------------------------
# Gregorian date from Julian Day (returns tuple)
def JDtoD(JD):
    Z = int(JD + 0.5)
    F = JD + 0.5 - Z
    if Z < 2299161:
        A = Z
    else:
        alpha = int((Z - 1867216.25) / 36524.25)
        A = Z + 1 + alpha - alpha // 4
    B = A + 1524
    C = int((B - 122.1) / 365.25)
    D = int(365.25 * C)
    E = int((B - D) / 30.6001)

    d = int(B - D - int(30.6001 * E) + F)
    if E < 14:
        m = E - 1
    else:
        m = E - 13
    if m > 2:
        y = C - 4716
    else:
        y = C - 4715

    h = int((JD + 1.5) % 7)
    hname = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
    hari = hname[h]

    FJD = (JD - int(JD)) - 0.5
    if FJD < 0:
        FJD = 1 + FJD
    hrs = int(FJD * 24)
    mnt = int((FJD * 24 - hrs) * 60)
    dtk = int(((FJD * 24 - hrs) * 60 - mnt) * 60)
    return d, m, y, hrs, mnt, dtk, hari


# ----------------------------------------------------------------------
# Solar position (geocentric)
def SolarPos(JDE):
    T = (JDE - 2451545.0) / 36525.0
    L0 = _deg_norm(280.46646 + 36000.76983 * T + 0.0003032 * T * T)
    M0 = _deg_norm(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    e = 0.016708634 - 0.000042037 * T - 0.0000001267 * T * T
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(math.radians(M0)) +
         (0.019993 - 0.000101 * T) * math.sin(2 * math.radians(M0)) +
         0.000289 * math.sin(3 * math.radians(M0)))
    C = _deg_norm(C)
    L = _deg_norm(L0 + C)
    M = _deg_norm(M0 + C)
    _Omega = _deg_norm(125.04 - 1934.136 * T)
    _lambda = _deg_norm(L - 0.00569 - 0.00478 * math.sin(math.radians(_Omega)))
    _beta = 0.0
    R = (1.000001018 * (1 - e * e)) / (1 + e * math.cos(math.radians(M)))
    R *= 149597870.7  # km

    # Obliquity
    _epsilon0 = (23 + 26 / 60.0 + 21.448 / 3600.0 -
                 4680.93 / 3600.0 * (T / 100) -
                 1.55 / 3600.0 * (T / 100) ** 2 +
                 1999.25 / 3600.0 * (T / 100) ** 3 -
                 51.38 / 3600.0 * (T / 100) ** 4)
    _L = _deg_norm(280.4665 + 36000.7698 * T)
    __L = _deg_norm(218.3165 + 481267.8813 * T)
    _depsilon = (9.2 / 3600.0 * math.cos(math.radians(_Omega)) +
                 0.57 / 3600.0 * math.cos(2 * math.radians(_L)) +
                 0.10 / 3600.0 * math.cos(2 * math.radians(__L)) -
                 0.09 / 3600.0 * math.cos(2 * math.radians(_Omega)))
    _depsilon = _deg_norm(_depsilon)
    _epsilon = _epsilon0 + _depsilon + 0.00256 * math.cos(math.radians(_Omega))

    # Right Ascension
    _alpha = math.degrees(
        math.atan2(
            math.cos(
                math.radians(_epsilon)) *
            math.sin(
                math.radians(_lambda)),
            math.cos(
                math.radians(_lambda))))
    _alpha = _deg_norm(_alpha)
    # Declination
    _delta = math.degrees(
        math.asin(
            math.sin(
                math.radians(_epsilon)) *
            math.sin(
                math.radians(_lambda))))
    _delta = _deg_norm(_delta)
    return R, _alpha, _delta, _lambda, _beta


# ----------------------------------------------------------------------
# Lunar position (geocentric)
def LunarPos(JDE):
    T = (JDE - 2451545.0) / 36525.0
    # Mean elements
    _L = _deg_norm(
        218.3164477 +
        481267.88123421 *
        T -
        0.0015786 *
        T *
        T +
        T ** 3 /
        538841 -
        T ** 4 /
        65194000)
    D = _deg_norm(
        297.8501921 +
        445267.1114034 *
        T -
        0.0018819 *
        T *
        T +
        T ** 3 /
        545868 -
        T ** 4 /
        113065000)
    M = _deg_norm(
        357.5291092 +
        35999.0502909 *
        T -
        0.0001536 *
        T *
        T +
        T ** 3 /
        24490000)
    _M = _deg_norm(
        134.9633964 +
        477198.8675055 *
        T +
        0.0087414 *
        T *
        T +
        T ** 3 /
        69699 -
        T ** 4 /
        14712000)
    F = _deg_norm(
        93.2720950 +
        483202.0175233 *
        T -
        0.0036539 *
        T *
        T -
        T ** 3 /
        3526000 +
        T ** 4 /
        863310000)

    A1 = _deg_norm(119.75 + 131.849 * T)
    A2 = _deg_norm(53.09 + 479264.29 * T)
    A3 = _deg_norm(313.45 + 481266.484 * T)

    E = 1 - 0.002516 * T - 0.0000074 * T * T

    # Correction tables (longitude and distance)
    lr = [
        [0, 0, 1, 0, 6288774, -20905335],
        [2, 0, -1, 0, 1274027, -3699111],
        [2, 0, 0, 0, 658314, -2955968],
        [0, 0, 2, 0, 213618, -569925],
        [0, 1, 0, 0, -185116, 48888],
        [0, 0, 0, 2, -114332, -3149],
        [2, 0, -2, 0, 58793, 246158],
        [2, -1, -1, 0, 57066, -152138],
        [2, 0, 1, 0, 53322, -170733],
        [2, -1, 0, 0, 45758, -204586],
        [0, 1, -1, 0, -40923, -129620],
        [1, 0, 0, 0, -34720, 108743],
        [0, 1, 1, 0, -30383, 104755],
        [2, 0, 0, -2, 15327, 10321],
        [0, 0, 1, 2, -12528, 0],
        [0, 0, 1, -2, 10980, 79661],
        [4, 0, -1, 0, 10675, -34782],
        [0, 0, 3, 0, 10034, -23210],
        [4, 0, -2, 0, 8548, -21636],
        [2, 1, -1, 0, -7888, 24208],
        [2, 1, 0, 0, -6766, 30824],
        [1, 0, -1, 0, -5163, -8379],
        [1, 1, 0, 0, 4987, -16675],
        [2, -1, 1, 0, 4036, -12831],
        [2, 0, 2, 0, 3994, -10445],
        [4, 0, 0, 0, 3861, -11650],
        [2, 0, -3, 0, 3665, 14403],
        [0, 1, -2, 0, -2689, -7003],
        [2, 0, -1, 2, -2602, 0],
        [2, -1, -2, 0, 2390, 10056],
        [1, 0, 1, 0, -2348, 6322],
        [2, -2, 0, 0, 2236, -9884],
        [0, 1, 2, 0, -2120, 5751],
        [0, 2, 0, 0, -2069, 0],
        [2, -2, -1, 0, 2048, -4950],
        [2, 0, 1, -2, -1773, 4130],
        [2, 0, 0, 2, -1595, 0],
        [4, -1, -1, 0, 1215, -3958],
        [0, 0, 2, 2, -1110, 0],
        [3, 0, -1, 0, -892, 3258],
        [2, 1, 1, 0, -810, 2616],
        [4, -1, -2, 0, 759, -1897],
        [0, 2, -1, 0, -713, -2117],
        [2, 2, -1, 0, -700, 2354],
        [2, 1, -2, 0, 691, 0],
        [2, -1, 0, -2, 596, 0],
        [4, 0, 1, 0, 549, -1423],
        [0, 0, 4, 0, 537, -1117],
        [4, -1, 0, 0, 520, -1571],
        [1, 0, -2, 0, -487, -1739],
        [2, 1, 0, -2, -399, 0],
        [0, 0, 2, -2, -381, -4421],
        [1, 1, 1, 0, 351, 0],
        [3, 0, -2, 0, -340, 0],
        [4, 0, -3, 0, 330, 0],
        [2, -1, 2, 0, 327, 0],
        [0, 2, 1, 0, -323, 1165],
        [1, 1, -1, 0, 299, 0],
        [2, 0, 3, 0, 294, 0],
        [2, 0, -1, -2, 0, 8752]
    ]

    # Latitude correction
    b = [
        [0, 0, 0, 1, 5128122],
        [0, 0, 1, 1, 280602],
        [0, 0, 1, -1, 277693],
        [2, 0, 0, -1, 173237],
        [2, 0, -1, 1, 55413],
        [2, 0, -1, -1, 46271],
        [2, 0, 0, 1, 32573],
        [0, 0, 2, 1, 17198],
        [2, 0, 1, -1, 9266],
        [0, 0, 2, -1, 8822],
        [2, -1, 0, -1, 8216],
        [2, 0, -2, -1, 4324],
        [2, 0, 1, 1, 4200],
        [2, 1, 0, -1, -3359],
        [2, -1, -1, 1, 2463],
        [2, -1, 0, 1, 2211],
        [2, -1, -1, -1, 2065],
        [0, 1, -1, -1, -1870],
        [4, 0, -1, -1, 1828],
        [0, 1, 0, 1, -1794],
        [0, 0, 0, 3, -1749],
        [0, 1, -1, 1, -1565],
        [1, 0, 0, 1, -1491],
        [0, 1, 1, 1, -1475],
        [0, 1, 1, -1, -1410],
        [0, 1, 0, -1, -1344],
        [1, 0, 0, -1, -1335],
        [0, 0, 3, 1, 1107],
        [4, 0, 0, -1, 1021],
        [4, 0, -1, 1, 833],
        [0, 0, 1, -3, 777],
        [4, 0, -2, 1, 671],
        [2, 0, 0, -3, 607],
        [2, 0, 2, -1, 596],
        [2, -1, 1, -1, 491],
        [2, 0, -2, 1, -451],
        [0, 0, 3, -1, 439],
        [2, 0, 2, 1, 422],
        [2, 0, -3, -1, 421],
        [2, 1, -1, 1, -366],
        [2, 1, 0, 1, -351],
        [4, 0, 0, 1, 331],
        [2, -1, 1, 1, 315],
        [2, -2, 0, -1, 302],
        [0, 0, 1, 3, -283],
        [2, 1, 1, -1, -229],
        [1, 1, 0, -1, 223],
        [1, 1, 0, 1, 223],
        [0, 1, -2, -1, -220],
        [2, 1, -2, -1, -220],
        [1, 0, 1, 1, -185],
        [2, -1, -2, -1, 181],
        [0, 1, 2, 1, -177],
        [4, 0, -2, -1, 176],
        [4, -1, -1, -1, 166],
        [1, 0, 1, -1, -164],
        [4, 0, 1, -1, 132],
        [1, 0, -1, -1, -119],
        [4, -1, 0, -1, 115],
        [2, -2, 0, 1, 107]
    ]

    suml = 0.0
    sumr = 0.0
    for k in lr:
        a = D * k[0] + M * k[1] + _M * k[2] + F * k[3]
        c = 1.0
        if abs(k[1]) == 1:
            c = E
        elif abs(k[1]) == 2:
            c = E * E
        suml += c * k[4] * math.sin(math.radians(a))
        sumr += c * k[5] * math.cos(math.radians(a))

    sumb = 0.0
    for k in b:
        a = D * k[0] + M * k[1] + _M * k[2] + F * k[3]
        c = 1.0
        if abs(k[1]) == 1:
            c = E
        elif abs(k[1]) == 2:
            c = E * E
        sumb += c * k[4] * math.sin(math.radians(a))

    suml += 3958 * math.sin(math.radians(A1)) + 1962 * \
        math.sin(math.radians(_L - F)) + 318 * math.sin(math.radians(A2))
    sumb += (-2235 * math.sin(math.radians(_L)) + 382 * math.sin(math.radians(A3)) +
             175 * math.sin(math.radians(A1 - F)) + 175 * math.sin(math.radians(A1 + F)) +
             127 * math.sin(math.radians(_L - _M)) - 115 * math.sin(math.radians(_L + _M)))

    _lambda0 = _L + suml / 1e6
    _beta = sumb / 1e6
    _Delta = 385000.56 + sumr / 1000.0  # km

    # Nutation
    _Omega = _deg_norm(
        125.04452 -
        1934.136261 *
        T +
        0.0020708 *
        T *
        T +
        T ** 3 /
        450000)
    _L_sun = _deg_norm(280.4665 + 36000.7698 * T)
    __L_moon = _deg_norm(218.3165 + 481267.8813 * T)
    _dPsi = (-17.20 / 3600.0 * math.sin(math.radians(_Omega)) +
             1.32 / 3600.0 * math.sin(2 * math.radians(_L_sun)) -
             0.23 / 3600.0 * math.sin(2 * math.radians(__L_moon)) +
             0.21 / 3600.0 * math.sin(2 * math.radians(_Omega)))
    _depsilon = (9.2 / 3600.0 * math.cos(math.radians(_Omega)) +
                 0.57 / 3600.0 * math.cos(2 * math.radians(_L_sun)) +
                 0.10 / 3600.0 * math.cos(2 * math.radians(__L_moon)) -
                 0.09 / 3600.0 * math.cos(2 * math.radians(_Omega)))
    _lambda = _lambda0 + _dPsi
    _epsilon0 = (23 + 26 / 60.0 + 21.448 / 3600.0 -
                 4680.93 / 3600.0 * (T / 100) -
                 1.55 / 3600.0 * (T / 100) ** 2 +
                 1999.25 / 3600.0 * (T / 100) ** 3 -
                 51.38 / 3600.0 * (T / 100) ** 4)
    _epsilon = _epsilon0 + _depsilon

    _alpha, _delta = EKLtoEKU(_lambda, _beta, _epsilon)
    return _Delta, _alpha, _delta, _lambda, _beta


# ----------------------------------------------------------------------
# Lunar illumination fraction (0-1)
def LunarIllum(JDE):
    _lambda_sun = SolarPos(JDE)[3]
    _lambda_moon = LunarPos(JDE)[3]
    D = _deg_norm(_lambda_moon - _lambda_sun)
    return 0.5 * (1 - math.cos(math.radians(D)))


# ----------------------------------------------------------------------
# Find Julian Day of a given lunar phase (k = 0 new moon, 0.25 first
# quarter, etc.)
def JDLunarPhase(k):
    T = k / 1236.85
    # Mean elements
    M = _deg_norm(
        2.5534 +
        29.1053567 *
        k -
        0.0000014 *
        T *
        T -
        0.00000011 *
        T ** 3)
    _M = _deg_norm(
        201.5643 +
        385.81693528 *
        k +
        0.0107528 *
        T *
        T +
        0.00001238 *
        T ** 3 -
        0.000000058 *
        T ** 4)
    F = _deg_norm(
        160.7108 +
        390.67050284 *
        k -
        0.0016118 *
        T *
        T -
        0.00000227 *
        T ** 3 +
        0.000000011 *
        T ** 4)
    _Omega = _deg_norm(
        124.7746 -
        1.56375588 *
        k +
        0.0020672 *
        T *
        T +
        0.00000215 *
        T ** 3)

    A1 = _deg_norm(299.77 + 0.107408 * k - 0.009173 * T * T)
    A2 = _deg_norm(251.88 + 0.016321 * k)
    A3 = _deg_norm(251.83 + 26.651886 * k)
    A4 = _deg_norm(349.42 + 36.412478 * k)
    A5 = _deg_norm(84.66 + 18.206239 * k)
    A6 = _deg_norm(141.74 + 53.303771 * k)
    A7 = _deg_norm(207.14 + 2.453732 * k)
    A8 = _deg_norm(154.84 + 7.306860 * k)
    A9 = _deg_norm(34.52 + 27.261239 * k)
    A10 = _deg_norm(207.19 + 0.121824 * k)
    A11 = _deg_norm(291.34 + 1.844379 * k)
    A12 = _deg_norm(161.72 + 24.198154 * k)
    A13 = _deg_norm(239.56 + 25.513099 * k)
    A14 = _deg_norm(331.55 + 3.592518 * k)

    E = 1 - 0.002516 * T - 0.0000074 * T * T

    # Correction coefficients for New Moon, Full Moon, Quarter
    corr = [
        [-0.4072, -0.40614, -0.62801, _M],
        [0.17241 * E, 0.17302 * E, 0.17172 * E, M],
        [0.01608, 0.01614, 0.00862, 2 * _M],
        [0.01039, 0.01043, 0.00804, 2 * F],
        [0.00739 * E, 0.00734 * E, 0.00454 * E, _M - M],
        [-0.00514 * E, -0.00515 * E, -0.01183 * E, _M + M],
        [0.00208 * E * E, 0.00209 * E * E, 0.00204 * E * E, 2 * M],
        [-0.00111, -0.00111, -0.0018, _M - 2 * F],
        [-0.00057, -0.00057, -0.0007, _M + 2 * F],
        [0.00056 * E, 0.00056 * E, 0.00027 * E, 2 * _M + M],
        [-0.00042, -0.00042, -0.0004, 3 * _M],
        [0.00042 * E, 0.00042 * E, 0.00032 * E, M + 2 * F],
        [0.00038 * E, 0.00038 * E, 0.00032 * E, M - 2 * F],
        [-0.00024 * E, -0.00024 * E, -0.00034 * E, 2 * _M - M],
        [-0.00017, -0.00017, -0.00017, _Omega],
        [-0.00007, -0.00007, -0.00028 * E * E, _M + 2 * M],
        [0.00004, 0.00004, 0.00002, 2 * _M - 2 * F],
        [0.00004, 0.00004, 0.00003, 3 * M],
        [0.00003, 0.00003, 0.00003, _M + M - 2 * F],
        [0.00003, 0.00003, 0.00004, 2 * _M + 2 * F],
        [-0.00003, -0.00003, -0.00004, _M + M + 2 * F],
        [0.00003, 0.00003, 0.00002, _M - M + 2 * F],
        [-0.00002, -0.00002, -0.00005, _M - M - 2 * F],
        [-0.00002, -0.00002, -0.00002, 3 * _M + M],
        [0.00002, 0.00002, 0.0, 4 * _M],
        [0.0, 0.0, 0.00004, _M - 2 * M]
    ]

    corrNew = 0.0
    corrFull = 0.0
    corrQuarter = 0.0
    for row in corr:
        corrNew += row[0] * math.sin(math.radians(row[3]))
        corrFull += row[1] * math.sin(math.radians(row[3]))
        corrQuarter += row[2] * math.sin(math.radians(row[3]))

    # Additional correction for quarter phases
    W = (0.00306 - 0.00038 * E * math.cos(math.radians(M)) +
         0.00026 * math.cos(math.radians(_M)) -
         0.00002 * math.cos(math.radians(_M - M)) +
         0.00002 * math.cos(math.radians(_M + M)) +
         0.00002 * math.cos(2 * math.radians(F)))

    addcorr = (0.000325 * math.sin(math.radians(A1)) +
               0.000165 * math.sin(math.radians(A2)) +
               0.000164 * math.sin(math.radians(A3)) +
               0.000126 * math.sin(math.radians(A4)) +
               0.000110 * math.sin(math.radians(A5)) +
               0.000062 * math.sin(math.radians(A6)) +
               0.000060 * math.sin(math.radians(A7)) +
               0.000056 * math.sin(math.radians(A8)) +
               0.000047 * math.sin(math.radians(A9)) +
               0.000042 * math.sin(math.radians(A10)) +
               0.000040 * math.sin(math.radians(A11)) +
               0.000037 * math.sin(math.radians(A12)) +
               0.000035 * math.sin(math.radians(A13)) +
               0.000023 * math.sin(math.radians(A14)))

    JDE = 2451550.09766 + 29.530588861 * k + 0.00015437 * \
        T * T - 0.00000015 * T ** 3 + 0.00000000073 * T ** 4
    frac = abs(k - int(k))
    if abs(frac) < 0.01:  # New Moon
        JDE += corrNew + addcorr
    elif abs(frac - 0.5) < 0.01:  # Full Moon
        JDE += corrFull + addcorr
    elif abs(frac - 0.25) < 0.01:  # First Quarter
        JDE += corrQuarter + addcorr + W
    elif abs(frac - 0.75) < 0.01:  # Last Quarter
        JDE += corrQuarter + addcorr - W
    return JDE


# ----------------------------------------------------------------------
# Helper: get phase name from k
def CheckState(k):
    frac = abs(k - int(k))
    if frac < 0.01:
        return "New Moon"
    elif abs(frac - 0.25) < 0.01:
        return "First Quarter"
    elif abs(frac - 0.5) < 0.01:
        return "Full Moon"
    elif abs(frac - 0.75) < 0.01:
        return "Third Quarter"
    return "Unknown"
