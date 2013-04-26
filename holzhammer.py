# -*- coding: utf-8 -*-

import math

def readfile(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f.readlines()]

def writefile(filename, gcode):
    with open(filename, 'w') as f:
        for line in gcode:
            f.write(line + '\n')

def getDifference(numa, numb):
    if numa >= numb: return numa - numb
    else: return numb - numa

class GCode(object):
    def __init__(self, filename, extruder, inittemp):
        self._gcode = readfile(filename)
        self._extruder = extruder
        self._inittemp = inittemp
    def dump(self):
        return writefile('out.bfb', self._gcode)

    def isMove(self, line):
        if 'G1 ' in line: return True
    def getXfromLine(self, line):
        if self.isMove(line): return float(line.split()[1].strip('X'))
    def getYfromLine(self, line):
        if self.isMove(line): return float(line.split()[2].strip('Y'))
    def getZfromLine(self, line):
        if self.isMove(line): return float(line.split()[3].strip('Z'))
    def getFfromLine(self, line):
        if self.isMove(line): return float(line.split()[4].strip('F'))
    def getSpeedfromLine(self, line):
        return float(self.getFfromLine(line) / 60)
    def getLinefromLnum(self, lnum):
        return self._gcode[lnum]
    def getLnumfromZ(self, z):
        for ln, line in enumerate(self._gcode):
            if self.getZfromLine(line) == z:
                return ln
    def getLnumofFirstObjectLayer(self):
        return [lnum for lnum, line in enumerate(self._gcode) if 'raftLayerEnd' in line][0]
    def getZofFirstObjectLayer(self):
        fline = self.getLinefromLnum(self.getLnumofFirstObjectLayer())
        fidx = 0
        while not self.getZfromLine(fline):
            fidx += 1
            fline = self.getLinefromLnum(self.getLnumofFirstObjectLayer() + fidx)
        return self.getZfromLine(fline)

    def killAllTemps(self):
        result = []
        firstseen = False
        for ln, line in enumerate(self._gcode):
            if self.getLnumofFirstObjectLayer() <= ln:
                if 'M%d04' %(self._extruder) in line:
                    if not firstseen:
                        result.append('M%d04 S%d' %(self._extruder, self._inittemp))
                        firstseen = True
                        print '-- lnum %d altered %s°' %(ln, line)
                    elif int(line.split()[1].strip('S')) != 0:
                        print '-- lnum %d killed %s°' %(ln, line)
                else:
                    result.append(line)
            else:
                result.append(line)
        self._gcode = result

    def getListofZ(self):
        result = set()
        fz = self.getZofFirstObjectLayer()
        for ln, line in enumerate(self._gcode):
            if self.getZfromLine(line) >= fz:
                result.add(self.getZfromLine(line))
        return sorted(result)

    def getZstepfromZ(self, z):
        if z == self.getListofZ()[-1]:
            return 0
        zpos = self.getListofZ().index(z)
        return self.getListofZ()[zpos+1] - self.getListofZ()[zpos]
    def getZsteps(self):
        return set(j-i for i, j in zip(self.getListofZ()[:-1], self.getListofZ()[1:]))

    def getSecsforZ(self, z):
        startlnum = self.getLnumfromZ(z)
        endlnum = self.getLnumfromZ(z + self.getZstepfromZ(z))
        if self.getZstepfromZ(z) == 0:
            endlnum = len(self._gcode)
        lastx = 0.0
        lasty = 0.0
        distance = 0.0
        seconds = 0.0
        for line in reversed(self._gcode[:startlnum]):
            if self.isMove(line):
                lastx = self.getXfromLine(line)
                lasty = self.getYfromLine(line)
                break
        for line in self._gcode[startlnum:endlnum]:
            if self.isMove(line):
                curx = self.getXfromLine(line)
                cury = self.getYfromLine(line)
                a = getDifference(lastx, curx)
                b = getDifference(lasty, cury)
                lastx = curx
                lasty = cury
                distance += math.sqrt((a*a)+(b*b))
                seconds += distance / self.getSpeedfromLine(line)
        return seconds

    def getListofZLnumandSecs(self):
        return [(element, self.getLnumfromZ(element), self.getSecsforZ(element)) for element in self.getListofZ()]

    def cycleHeatuntilZ(self, targetz, starttemp, targettemp):
        span = getDifference(starttemp, targettemp)
        if targettemp == starttemp:
            return None
        elif targettemp >= starttemp:
            temp = targettemp
        else:
            temp = targettemp
        lpos = self.getListofZ().index(targetz)
        for z, lnum, sec in reversed(self.getListofZLnumandSecs()[lpos - span:lpos + 1]):
            if sec >= 2.0:
                self._gcode.insert(lnum, 'M%d04 S%d' %(self._extruder, temp))
                print '-- layer %s at lnum %d -> %d°' %(z, lnum, temp)
                if targettemp >= starttemp:
                    temp -= 1
                else:
                    temp += 1
            else: print 'this should not happen'


def main():
    # ~> GCode(dateiname, extruder, start_temperatur)
    g = GCode('input.bfb', 1, 195)
    # print 'INIT: %s Layers' %(len(g.getListofZ()))
    # print 'getLnumfromZ(6.0) %s' %(g.getLnumfromZ(6.0))
    # print 'getLumofFirstObjectLayer %s' %(g.getLnumofFirstObjectLayer())
    # print 'getZofFirstObjectLayer %s' %(g.getZofFirstObjectLayer())
    # print 'getZstepfromZ(6.0) %s' %(g.getZstepfromZ(6.0))
    # print 'getZsteps %s' %(g.getZsteps())
    # print 'getSecsforZ(6.0) %s' %(g.getSecsforZ(6.0))

    # alte Temperaturwerte entfernen
    g.killAllTemps()

    # Verläufe setzen ~> cycleHeatuntilZ(layer, start_temperatur, ziel_temperatur)
    g.cycleHeatuntilZ(6.0, 195, 199)

    g.cycleHeatuntilZ(11.0, 199, 190)

    # speichern
    g.dump()
    print 'return 0;'

if __name__ == '__main__':
    main()

