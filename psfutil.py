### psfutil - PSF font utility ###
# Uses https://git.kernel.org/pub/scm/linux/kernel/git/legion/kbd.git/tree/src/psf.h?id=82dd58358bd341f8ad71155a53a561cf311ac974 as reference for PSF font format

import argparse


def getArgs():
    parser = argparse.ArgumentParser(prog='psfutil')
    parser.add_argument(
        'infile',
        help='Input file',
        type=str
    )
    parser.add_argument(
        'index',
        help='debug thing',
        type=int
    )

    return parser.parse_args()


class psf():
    # Python is big-endian, C is little-endian
    # Magic numbers here appear backwards to the magic number defined in kernel/git/legion/kbd.git as a result
    PSF1_MAGIC_NUMBER       = 0x0435
    PSF1_MODE_512           = 0x01
    PSF1_MODE_HASTAB        = 0x02
    PSF1_MODE_HASSEQ        = 0x04
    PSF1_MAX_MODE           = 0x05
    PSF1_SEP                = 0xFFFF
    PSF1_SEQ                = 0xFFFE

    PSF2_FLAG_HAS_UNICODE   = 0x01
    PSF2_MAGIC_NUMBER       = 0x864AB572
    PSF2_MAXVERSION         = 0
    PSF2_SEP                = 0xFF
    PSF2_SEQ                = 0xFE

    def __init__(self, version: int, flags: int, height: int, width: int):
        self.version = version
        self.flags = flags
        self.charSize = height * ((width + 7) // 8)
        self.height = height
        self.width = width
        self.length = 0
        self.glyphs = []

    def __repr__(self):
        return 'psf(version={}, flags={}, length={}, charSize={}, height={}, width={})'.format(self.version, self.flags, self.length, self.charSize, self.height, self.width)

    __str__ = __repr__

    def addGlyph(self, pixels):
        if len(pixels) != self.height * self.width: raise ValueError('{} pixels is incorrect for {}x{}'.format(len(pixels), self.height, self.width))
        self.glyphs.append(pixels)
        self.length = len(self.glyphs)

    def renderGlyph(self, index):
        glyph = self.glyphs[index]
        for y in range(self.height):
            print(' '.join(['#' if bit else ' ' for bit in glyph[y * self.width:(y + 1) * self.width]]))

def readPSF(binary):
    print('Header begins at 0x0')
    if int.from_bytes(binary[0:2], 'little') == psf.PSF1_MAGIC_NUMBER:
        raise NotImplementedError('PSF 1 support not implemented')
    
    elif int.from_bytes(binary[0:4], 'little') == psf.PSF2_MAGIC_NUMBER:
        version     = int.from_bytes(binary[4:8],   'little')
        headerSize  = int.from_bytes(binary[8:12],  'little')
        flags       = int.from_bytes(binary[12:16], 'little')
        length      = int.from_bytes(binary[16:20], 'little')
        charSize    = int.from_bytes(binary[20:24], 'little')   # Number of bytes per glyph
        height      = int.from_bytes(binary[24:28], 'little')
        width       = int.from_bytes(binary[28:32], 'little')
        
        font = psf(version, flags, height, width)

        if charSize != font.charSize: raise ValueError('Invalid font data (bad charSize)')

        print('Font data begins at 0x{:X}'.format(headerSize))
        rowSize = charSize // height    # Number of bytes per row
        for i0 in range(length):
            pixels = []
            for y in range(height):
                # Comment examples are assuming 8x5 fontface
                rowBytes = binary[headerSize + (charSize * i0):headerSize + (charSize * i0) + (rowSize * y)]  # Ex. 0x58
                rowInt = int.from_bytes(rowBytes, 'big')    # Ex. 0b01011000
                rowInt >> (rowSize * 8) - width     # Ex. 0b01011
                for i1 in range(width - 1, -1, -1):
                    pixels.append((rowInt & (2 ** i1)) >> i1)
            font.addGlyph(pixels)

        if flags & psf.PSF2_FLAG_HAS_UNICODE:

            unicodeStart = headerSize + charSize * length
            print('Unicode data begins at 0x{:X}'.format(unicodeStart))

        else:
            raise ValueError('Font has no unicode table')

        return font

    else:
        raise ValueError('Invalid font data (bad magic number)')


if __name__ == '__main__':
    args = getArgs()

    with open(args.infile, 'rb') as infile:
        f = readPSF(infile.read())
        print(f)
        f.renderGlyph(args.index)

