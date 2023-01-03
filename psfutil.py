### psfutil - PSF font utility ###
# Uses https://git.kernel.org/pub/scm/linux/kernel/git/legion/kbd.git/tree/src/psf.h?id=82dd58358bd341f8ad71155a53a561cf311ac974 as reference for PSF font format

import argparse


_version = '0.0.1'


def getArgs():
    rootParser = argparse.ArgumentParser(prog='psfutil')
    subParsers = rootParser.add_subparsers(dest='command')
    subParsers.required = True

    showParser = subParsers.add_parser('show')
    showParser.set_defaults(function=command_show)
    showParser.add_argument(
        'infile',
        help='Input file',
        type=str
    )
    showParser.add_argument(
        'glyph',
        help='Glyph to show',
        type=str
    )
    showParser.add_argument(
        '-f',
        '--format',
        help='Glyph input format (t=text, i=index)',
        type=str,
        default='t',
    )

    return rootParser.parse_args()


class psf():
    # Python is big-endian, C is little-endian
    # Magic numbers here appear backwards to the magic number defined in kernel/git/legion/kbd.git as a result
    PSF1_MAGIC_NUMBER       = 0x0435
    PSF1_MODE_512           = 0x01
    PSF1_MODE_HASTAB        = 0x02
    PSF1_MODE_HASSEQ        = 0x04
    PSF1_MAX_MODE           = 0x05
    PSF1_SEP                = 0xFFFF
    PSF1_SEQ                = 0xEFFF

    PSF2_FLAG_HAS_UNICODE   = 0x01
    PSF2_MAGIC_NUMBER       = 0x864AB572
    PSF2_MAXVERSION         = 0
    PSF2_SEP                = 0xFF
    PSF2_SEQ                = 0xEF

    def __init__(self, version: int, flags: int, height: int, width: int, length: int):
        self.version = version
        self.flags = flags
        self.charSize = height * ((width + 7) // 8)
        self.height = height
        self.width = width
        self.length = length
        self.glyphs = []
        self.charMap = {}

    def __repr__(self):
        return 'psf(version={}, flags={}, length={}, charSize={}, height={}, width={})'.format(self.version, self.flags, self.length, self.charSize, self.height, self.width)

    __str__ = __repr__

    def addGlyph(self, pixels):
        if len(pixels) != self.height * self.width: raise ValueError('{} pixels is incorrect for {}x{}'.format(len(pixels), self.height, self.width))
        if len(self.glyphs) >= self.length: raise ValueError('Cannot add glyph (max {})'.format(self.length))
        self.glyphs.append(pixels)

    def renderGlyph(self, index):
        glyph = self.glyphs[index]
        for y in range(self.height):
            print(' '.join(['#' if bit else ' ' for bit in glyph[y * self.width:(y + 1) * self.width]]))

def readPSF(binary):
    # print('Header begins at 0x0')
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
        
        font = psf(version, flags, height, width, length)

        if charSize != font.charSize: raise ValueError('Invalid font data (bad charSize)')

        # print('Font data begins at 0x{:X}'.format(headerSize))
        rowSize = charSize // height    # Number of bytes per row
        for i0 in range(length):
            pixels = []
            for y in range(height):
                # Comment examples are assuming 8x5 fontface
                rowBytes = binary[headerSize + (charSize * i0) + (rowSize * y):headerSize + (charSize * i0) + (rowSize * (y + 1))]  # Ex. 0x58
                rowInt = int.from_bytes(rowBytes, 'big')    # Ex. 0b01011000
                rowInt >>= (rowSize * 8) - width     # Ex. 0b01011
                for i1 in range(width - 1, -1, -1):
                    pixels.append((rowInt & (2 ** i1)) >> i1)
            font.addGlyph(pixels)

        if flags & psf.PSF2_FLAG_HAS_UNICODE:

            unicodeStart = headerSize + charSize * length
            # print('Unicode data begins at 0x{:X}'.format(unicodeStart))

            ptr = unicodeStart
            for i in range(length):
                byte = -1
                while byte != psf.PSF2_SEP:
                    byte = binary[ptr]; ptr += 1
                    data = b''
                    while not byte in (psf.PSF2_SEQ, psf.PSF2_SEP):
                        data += byte.to_bytes(1, 'big')
                        byte = binary[ptr]; ptr += 1

                    try:
                        chars = data.decode()
                        for char in chars:
                            font.charMap[char] = i

                    except UnicodeDecodeError:
                        print('WARNING: Unable to decode {} for glyph {}, skipping character(s)'.format(data, i0))

        else:
            raise ValueError('Font has no unicode table')

        return font

    else:
        raise ValueError('Invalid font data (bad magic number)')


def command_show(args):
    with open(args.infile, 'rb') as infile:
        font = readPSF(infile.read())

    if args.format in ('t', 'text'):
        index = font.charMap[args.glyph]
        if index is None: raise ValueError('Glyph not found in font')
    
    elif args.format in ('i', 'index'):
        index = int(args.glyph)

    else:
        raise ValueError('Invalid format: {}'.format(args.format))

    font.renderGlyph(index)


if __name__ == '__main__':
    print('PC Screen Font Utility v{}'.format(_version))
    args = getArgs()

    args.function(args)
