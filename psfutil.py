### psfutil - PC Screen Font Utility ###
# Uses https://git.kernel.org/pub/scm/linux/kernel/git/legion/kbd.git/tree/src/psf.h?id=82dd58358bd341f8ad71155a53a561cf311ac974 as reference for PSF font format
# See https://github.com/AwesomeCronk/psfutil/blob/master/LICENSE for license


import argparse, sys

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


_version = '0.0.1'


def getArgs():
    rootParser = argparse.ArgumentParser(prog='psfutil')
    subParsers = rootParser.add_subparsers(dest='command')
    subParsers.required = True

    showParser = subParsers.add_parser('show', help='Show a glyph')
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

    ttf2psfParser = subParsers.add_parser('ttf2psf', help='Convert ttf or otf font to psf')
    ttf2psfParser.set_defaults(function=command_ttf2psf)
    ttf2psfParser.add_argument(
        'infile',
        help='Input ttf file',
        type=str
    )
    ttf2psfParser.add_argument(
        'height',
        help='Height of glyphs',
        type=int
    )
    ttf2psfParser.add_argument(
        '-o',
        '--outfile',
        help='Output psf file',
        type=str,
        default='font.psf'
    )
    ttf2psfParser.add_argument(
        '-t',
        '--thres',
        help='Brightness threshold to accoutn for antialiasing',
        type=int,
        default=0.5
    )

    return rootParser.parse_args()


class psf():
    # Hex constants in Python are big-endian, in C they are little-endian
    # Constants here appear backwards to those defined in kernel/git/legion/kbd.git as a result
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
        print('-' * ((self.width * 2) + 3))
        for y in range(self.height):
            print('| ' + ' '.join(['#' if bit else ' ' for bit in glyph[y * self.width:(y + 1) * self.width]]) + ' |')
        print('-' * ((self.width * 2) + 4))

def readPSF(binary: bytes):
    # print('Header begins at 0x0')
    if int.from_bytes(binary[0:2], 'little') == psf.PSF1_MAGIC_NUMBER:
        print('ERROR: PSF 1 support not implemented'); sys.exit(1)
    
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

def writePSF(font: psf, PSF2=True):
    if not PSF2: print('ERROR: Cannot export to PSF1 format'); sys.exit(1)
    headerSize = (8 * 4).to_bytes(4, 'little')
    rowSize = (font.width // 8 + (1 if font.width % 8 else 0))
    charSize = font.height * rowSize
    binary = b''
    binary += psf.PSF2_MAGIC_NUMBER.to_bytes(4, 'little')
    binary += font.version.to_bytes(4, 'little')
    binary += headerSize
    binary += font.flags.to_bytes(4, 'little')
    binary += font.length.to_bytes(4, 'little')
    binary += charSize
    binary += font.height.to_bytes(4, 'little')
    binary += font.width.to_bytes(4, 'little')

    for glyph in font.glyphs:
        for y in range(font.height):
            rowBits = glyph[font.width * y:font.width * (y + 1)]
            rowInt = 0
            for rowBit in rowBits:
                rowInt += rowBit
                rowInt << 1
            rowInt << rowSize - font.width
            binary += rowInt.to_bytes(rowSize, 'big')

    for i0 in range(font.length):
        chars = ''
        for i1, id in enumerate(font.charMap.values()):
            if id == i0: chars += font.charMap.keys()[i1]
        print(chars)


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

def command_ttf2psf(args):
    # Get characters
    ttfFont = TTFont(args.infile)
    charIDs = []
    for table in ttfFont['cmap'].tables:
        charIDs += list(table.cmap.keys())
    for charID in charIDs:
        while charIDs.count(charID) > 1:
            charIDs.remove(charID)
    chars = []
    for charID in charIDs:
        try: chars.append(int.to_bytes(charID, 1, 'big').decode())
        except: print('WARNING: Could not decode char with id {}'.format(charID))

    img = Image.new('RGB', (args.height * 2, args.height))
    draw = ImageDraw.Draw(img)
    ttfFont = ImageFont.truetype(args.infile, args.height)

    draw.text((0, 0), 'A', font=ttfFont)
    img = img.crop((0, 0, ttfFont.getlength('A'), args.height))

    pixels = []
    for y in range(img.height):
        for x in range(img.width):
            if img.getpixel((x, y))[0] >= args.thres * 255:
                pixels.append(1); img.putpixel((x, y), (255, 255, 255))
            else:
                pixels.append(0); img.putpixel((x, y), (0, 0, 0))
    
    width = img.width
    height = args.height
    glyph = pixels

    print('-' * ((width * 2) + 3))
    for y in range(height):
        print('| ' + ' '.join(['#' if bit else ' ' for bit in glyph[y * width:(y + 1) * width]]) + ' |')
    print('-' * ((width * 2) + 4))

    img.show()


if __name__ == '__main__':
    print('PC Screen Font Utility v{}'.format(_version))
    args = getArgs()

    args.function(args)
