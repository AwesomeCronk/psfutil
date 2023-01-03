### psfutil - PC Screen Font Utility ###
# Uses https://git.kernel.org/pub/scm/linux/kernel/git/legion/kbd.git/tree/src/psf.h?id=82dd58358bd341f8ad71155a53a561cf311ac974 as reference for PSF font format
# See https://github.com/AwesomeCronk/psfutil/blob/master/LICENSE for license


import argparse, sys

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


_version = '1.0.0'


def getArgs():
    rootParser = argparse.ArgumentParser(
        prog='psfutil',
        description='See https://github.com/AwesomeCronk/psfutil for help or to raise an issue'
    )
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
        type=float,
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
        if len(pixels) != self.height * self.width: print('ERROR: {} pixels is incorrect for {}x{}'.format(len(pixels), self.height, self.width)); sys.exit(1)
        if len(self.glyphs) >= self.length: print('ERROR: Cannot add glyph (max {})'.format(self.length)); sys.exit(1)
        self.glyphs.append(pixels)

    def renderGlyph(self, index):
        glyph = self.glyphs[index]
        bar = '-' * ((self.width * 2) + 3)
        print(bar)
        for y in range(self.height):
            print('| ' + ' '.join(['#' if bit else ' ' for bit in glyph[y * self.width:(y + 1) * self.width]]) + ' |')
        print(bar)

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

        if charSize != font.charSize: print('ERROR: Invalid font data (bad charSize)'); sys.exit(1)

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
            print('ERROR: Font has no unicode table'); sys.exit(1)

        return font

    else:
        print('ERROR: Invalid font data (bad magic number)'); sys.exit(1)

def writePSF(font: psf, PSF2=True):
    if not PSF2: print('ERROR: Cannot export to PSF1 format'); sys.exit(1)
    binary = b''

    # Write header
    headerSize = (8 * 4)
    rowSize = (font.width // 8 + (1 if font.width % 8 else 0))
    charSize = font.height * rowSize

    binary += psf.PSF2_MAGIC_NUMBER.to_bytes(4, 'little')
    binary += font.version.to_bytes(4, 'little')
    binary += headerSize.to_bytes(4, 'little')
    binary += font.flags.to_bytes(4, 'little')
    binary += font.length.to_bytes(4, 'little')
    binary += charSize.to_bytes(4, 'little')
    binary += font.height.to_bytes(4, 'little')
    binary += font.width.to_bytes(4, 'little')

    # Write glyphs
    for glyph in font.glyphs:
        for y in range(font.height):
            rowBits = glyph[font.width * y:font.width * (y + 1)]
            rowInt = 0
            for rowBit in rowBits:
                rowInt |= rowBit
                rowInt <<= 1
            rowInt << (rowSize * 8) - font.width
            binary += rowInt.to_bytes(rowSize, 'big')

    if font.flags & psf.PSF2_FLAG_HAS_UNICODE:
        # Write unicode table
        for i0 in range(font.length):
            chars = ''
            charMapKeys = list(font.charMap.keys())
            for i1, id in enumerate(font.charMap.values()):
                if id == i0: chars += charMapKeys[i1]
            # print(chars)

            binary += chars.encode()
            binary += psf.PSF2_SEP.to_bytes(1, 'little')

    return binary


def command_show(args):
    with open(args.infile, 'rb') as infile:
        font = readPSF(infile.read())

    if args.format in ('t', 'text'):
        index = font.charMap[args.glyph]
        if index is None: print('ERROR: Glyph not found in font'); sys.exit(1)
    
    elif args.format in ('i', 'index'):
        index = int(args.glyph)

    else:
        print('ERROR: Invalid format: {}'.format(args.format)); sys.exit(1)

    font.renderGlyph(index)

def command_ttf2psf(args):
    # Get characters from TTF
    ttfFont = TTFont(args.infile)
    charIDs = []
    for table in ttfFont['cmap'].tables:
        charIDs += list(table.cmap.keys())
    for charID in charIDs:
        while charIDs.count(charID) > 1:
            charIDs.remove(charID)
    chars = []
    for charID in charIDs:
        try: chars.append(chr(charID))
        except: print('WARNING: Could not decode char with id {}'.format(charID))


    # Find max width
    ttfFont = ImageFont.truetype(args.infile, args.height)
    width = max([int(ttfFont.getlength(char)) for char in chars])
    print('Character width: {}'.format(width))

    # Set up rendering and initialize PSF font object
    img = Image.new('RGB', (width, args.height))
    draw = ImageDraw.Draw(img)
    psfFont = psf(0, 0, args.height, width, len(chars))
    # psfFont = psf(0, 0, args.height, width, 2)
    psfFont.flags |= psf.PSF2_FLAG_HAS_UNICODE
    
    # Resolve glyphs
    for c, char in enumerate(chars):
    # for c, char in enumerate(('A', 'B')):
            
        draw.text((0, 0), char, font=ttfFont)

        pixels = []
        for y in range(img.height):
            for x in range(img.width):
                if img.getpixel((x, y))[0] >= args.thres * 255:
                    pixels.append(1)
                else:
                    pixels.append(0)
                img.putpixel((x, y), (0, 0, 0))
        
        psfFont.addGlyph(pixels)
        psfFont.charMap[char] = c
        # psfFont.renderGlyph(c)

    binary = writePSF(psfFont, PSF2=True)
    with open(args.outfile, 'wb') as outfile:
        outfile.write(binary)
    


if __name__ == '__main__':
    print('PC Screen Font Utility v{}'.format(_version))
    args = getArgs()

    args.function(args)
