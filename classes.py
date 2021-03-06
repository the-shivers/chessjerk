#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Some classes for setting up a simple chess-bot.
"""

# Package import statements
import numpy as np
from random import sample
from pretty_board import pretty_board
from flavor import flavor_spitter


# Define Constants
color_list = ['white', 'black']
pawn_dir = dict(zip(color_list, [1, -1]))
x_index = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
y_index = [1, 2, 3, 4, 5, 6, 7, 8]
lookup_dict = {} # Use numbers to get letter/number indices
rev_lookup = {} # Use letter/number indices to get numbers
for x in range(8):
    for y in range(8):
        lookup_dict[(x,y)] = x_index[x] + '_' + str(y_index[y])
        rev_lookup['_'.join([x_index[x], str(y_index[y])])] = (x,y)


# Define Functions
def get_btwn(pos, new_pos):
    """Returns list of tuples between pos tuple and new_pos tuple.
    (1,2) and (3,4) would return [(2,3)]"""
    x_btwn = list(range(pos[0] + 1, new_pos[0]))
    # Logic if first x is larger than second x
    x_btwn = list(range(pos[0] - 1, new_pos[0], -1)) if not x_btwn else x_btwn
    y_btwn = list(range(pos[1] + 1, new_pos[1]))
    # Logic if first y is larger than second y
    y_btwn = list(range(pos[1] - 1, new_pos[1], -1)) if not y_btwn else y_btwn
    # Lists must be equal, even if only moving in x or y direction
    x_btwn = [pos[0]] * len(y_btwn) if len(x_btwn) < len(y_btwn) else x_btwn
    y_btwn = [pos[1]] * len(x_btwn) if len(x_btwn) > len(y_btwn) else y_btwn
    return [(x, y) for x, y in zip(x_btwn, y_btwn)]


# Define Classes
class CustArray:
    """A custom array to hold Piece and Square data. Size varies based on the
    information it needs to hold. For in_bound, unobstructed, valid moves, and
    targets this is 27. Move history is more, rest are intuitive."""
    dtype = [('field', (np.str_, 10)), ('x', np.int8), ('y', np.int8)]
    size_dict = {
        'ib_moves': 27, # Most possible moves is 27 by the queen
        'uo_moves': 27,
        'v_moves': 27,
        'hist': 100, # A single piece is not likely to be moved more
        'sq_tgts': 27,
        'backing_up': 15, # 15 allied pieces
        'backups': 15, # 15 allied pieces
        'targets': 8, # Queen and Knight can only attack 8
        'threats': 16, # 16 enemy pieces
        }

    def __init__(self, array_type):
        n = CustArray.size_dict[array_type]
        self.array_type = array_type
        self.array = np.empty((n,),dtype=CustArray.dtype)
        self.len = 0

    def __repr__(self):
        return repr(self.array)

    def __iter__(self):
        self.curr_index = 0
        return self

    def __next__(self):
        if self.curr_index < self.len:
            val = self.array[self.curr_index]
            self.curr_index = self.curr_index + 1
            return val
        else:
            raise StopIteration

    def add(self, obj):
        """Insert an item into next position of array."""
        self.array = np.insert(self.array, self.len, obj)
        self.len += 1

    def reset(self):
        """Reset the array to being filled with zeros."""
        n = CustArray.size_dict[self.array_type]
        self.array = np.empty((n,),dtype=CustArray.dtype)
        self.len = 0

    def filt(self, objs):
        """Return filtered array based on list of (field, val) tuples."""
        filt = (self.array[objs[0][0]] == objs[0][1])
        for i in objs[1:]:
            filt = (filt) & (self.array[i[0]] == i[1])
        return self.array[filt]

    def __getitem__(self, sliced):
        return self.array[sliced]


class ChessSquare:
    """Class representing game squares with info about surroundings."""
    def __init__(self, color, x, y, occ=None):
        self.color = color
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.occ = occ

    def __repr__(self):
        return self.color.title() + " square at " + str(self.pos)

class Piece():
    """Class representing game pieces and holding info about their position."""
    def __init__(self, color, piece_type, x, y):
        self.color = color
        self.type = piece_type
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.symbol = color[0].upper() + "_" + piece_type.title()
        self.kill_list = []
        self.ib_moves = CustArray('ib_moves')
        self.uo_moves = CustArray('uo_moves')
        self.v_moves = CustArray('v_moves')
        self.hist = CustArray('hist')
        self.backups = CustArray('backups')
        self.backing_up = CustArray('backing_up')
        self.targets = CustArray('targets')
        self.threats = CustArray('threats')

    def __repr__(self):
        return self.symbol + " at " + str(self.pos)

    def info(self):
        """Gets attributes for the piece"""

        def ti(tuple_list):
            """takes a tuple turns it into a tuple with a7 style indexing"""
            new_list = []
            for i, j, k in tuple_list:
                new_pos = lookup_dict[(j, k)].split('_')
                new_list += [(i, new_pos[0].upper()+str(new_pos[1]))]
            return new_list

        new_pos = "".join(lookup_dict[self.pos].split('_')).upper()
        print(self.symbol + " on " + new_pos + ".")
        print("\nNote: Valid moves does not consider check!")
        print("Valid moves: " + str(ti(self.v_moves)))
        print("Move history: " + str(ti(self.hist)))
        print("Backed up by: " + str(ti(self.backups)))
        print("Backing up: " + str(ti(self.backing_up)))
        print("Targeting: " + str(ti(self.targets)))
        print("Targeted by: " + str(ti(self.threats)))
        print("Killed: " + str(self.kill_list))

    def get_dest(self, x_diff, y_diff):
        """Returns destination given some difference from the orig. position"""
        return self.x + x_diff, self.y + y_diff

    def get_pawn_ib_moves(self):
        """All possible in-bounds moves for pawn. Includes en passant."""
        assert self.type == "pawn"
        p_num, p_dir = (-1, 's') if self.color == 'black' else (1, 'n')
        moves = {
            p_dir + '_1': self.get_dest(0, p_num),
            p_dir + '_2': self.get_dest(0, p_num * 2),
            p_dir + 'e_1': self.get_dest(1, p_num),
            p_dir + 'w_1': self.get_dest(-1, p_num)
            }
        # Add in-bound moves to ib_moves
        for move, dest in moves.items():
            if max(dest) <= 7 and min(dest) >= 0: # Ensure in-bounds
                self.ib_moves.add((move, *dest))

    def get_rook_ib_moves(self):
        """Get all possible moves for rook (or queen) that stay in-bounds.
        Does not consider castling, which is attributed to the King."""
        assert self.type == 'rook' or self.type == 'queen'
        n_moves = {'n_' + str(i): (self.x, i) for i in range(8) if i < self.y}
        e_moves = {'e_' + str(i): (i, self.y) for i in range(8) if i > self.x}
        s_moves = {'s_' + str(i): (self.x, i) for i in range(8) if i > self.y}
        w_moves = {'w_' + str(i): (i, self.y) for i in range(8) if i < self.x}
        moves = {**n_moves, **e_moves, **s_moves, **w_moves}
        [self.ib_moves.add((move, *dest)) for move, dest in moves.items()]

    def get_bishop_ib_moves(self):
        """Get all possible moves for bishop (or queen) that stay in-bounds."""
        assert self.type == 'bishop' or self.type == 'queen'
        ne_dests = {'ne_' + str(i): (self.x + i, self.y - i) for i in
                    range(1,8) if self.x + i < 8 and self.y - i > -1}
        se_dests = {'se_' + str(i): (self.x + i, self.y + i) for i in
                    range(1,8) if self.x + i < 8 and self.y + i < 8}
        sw_dests = {'sw_' + str(i): (self.x - i, self.y + i) for i in
                    range(1,8) if self.x - i > -1 and self.y + i < 8}
        nw_dests = {'nw_' + str(i): (self.x - i, self.y - i) for i in
                    range(1,8) if self.x - i > -1 and self.y - i > -1}
        moves = {**ne_dests, **se_dests, **sw_dests, **nw_dests}
        [self.ib_moves.add((move, *dest)) for move, dest in moves.items()]

    def get_knight_ib_moves(self):
        """Gets all possible moves for knight that stay in-bounds."""
        assert self.type == 'knight'
        diffs = {'nne_': (1, -2), 'ene_': (2, -1), 'ese_':(2, 1),
                 'sse_': (1, 2), 'ssw_': (-1, 2), 'wsw_':(-2, 1),
                 'wnw_': (-2, -1), 'nnw_': (-1, -2)}
        moves = {move: self.get_dest(*diff) for move, diff in diffs.items()}
        # Add in-bound moves to ib_moves
        for move, dest in moves.items():
            if max(dest) <= 7 and min(dest) >= 0: # Ensure in-bounds
                self.ib_moves.add((move, *dest))

    def get_queen_ib_moves(self):
        assert self.type == 'queen'
        self.get_bishop_ib_moves()
        self.get_rook_ib_moves()

    def get_king_ib_moves(self):
        """Gets all possible non-castle moves for king that stay in-bounds."""
        assert self.type == 'king'
        diffs = {'n_1': (0, -1), 'ne_1': (1, -1), 'e_1':(1, 0),
                 'se_1': (1, 1), 's_1': (0, 1), 'sw_1':(-1, 1),
                 'w_1': (-1, 0), 'nw_1': (-1, -1)}
        moves = {move: self.get_dest(*diff) for move, diff in diffs.items()}
        # Add in-bound moves to ib_moves
        for move, dest in moves.items():
            if max(dest) <= 7 and min(dest) >= 0: # Ensure in-bounds
                self.ib_moves.add((move, *dest))

    def get_ib_moves(self):
        """Gets all in-bound moves for a piece based on the piece type."""
        self.ib_moves.reset()
        move_dict = {
        'pawn':self.get_pawn_ib_moves,
        'rook':self.get_rook_ib_moves,
        'knight':self.get_knight_ib_moves,
        'bishop':self.get_bishop_ib_moves,
        'queen':self.get_queen_ib_moves,
        'king':self.get_king_ib_moves
        }
        return move_dict[self.type]()


class Chessboard:
    """A class used to hold squares and pieces as well as help those objects
    understand their surroundings. Also handles moves."""
    def __init__(self, turn='white', player_color = 'white'):
        flipper = 0 # flips between 0 and 1 each iteration
        row_list = []
        for y in range(8):
            square_list = []
            for x in range(8):
                square = ChessSquare(color_list[flipper], x, y)
                square_list = square_list + [square]
                flipper = flipper * -1 + 1
            row_list = row_list + [square_list]
        self.board = np.array(row_list)
        self.turn = turn
        self.nonturn = 'black' if turn == 'white' else 'white'
        self.turn_num = 1
        self.last_capture_turn = 1
        self.alive = []
        self.player_color = player_color
        self.move_history = []

    def __getitem__(self, tup):
        return self.board[tup[1],tup[0]]

    def set_up_board(self):
        """Puts pieces in starting positions."""
        piece_list = ['rook', 'knight', 'bishop', 'queen',
                      'king', 'bishop', 'knight', 'rook']
        for x, piece in enumerate(piece_list):
            for y, color in zip([0, 7], color_list):
                self[x,y].occ = Piece(color, piece, x, y)
            for y, color in zip([1, 6], color_list):
                self[x,y].occ = Piece(color, 'pawn', x, y)

    def set_up_board_randomly(self):
        """Puts starting pieces in randomly assigned positions. For testing."""
        full_pos_list = [(x,y) for x in range(8) for y in range(8)]
        pos_list = sample(full_pos_list, 32)
        piece_list = ['rook','knight','bishop']*2+['king','queen']+['pawn']*8
        color_list = np.repeat(sample(color_list, 2), 16)
        for color, pos, piece in zip(color_list, pos_list, piece_list*2):
            self[pos].occ=Piece(color,piece,pos[0],pos[1])
            self[pos].occ.has_moved = True

    def view(self, reverse = False):
        """Returns nice-looking view of board. Not used in calculations."""
        pretty_board(self, reverse)

    def get_pieces(self, piece_type=[], color=[]):
        """Returns a list of pieces meeting the parameters (and, not or).
        Ex: if you provide king, queen and no color, it gets 4 pieces.
        Ex: If you provide king, queen and white, it gets 2 pieces."""
        piece_list = []
        for x in range(8):
            for y in range(8):
                if self[x,y].occ:
                    piece_list = piece_list + [self[x,y].occ]
        if color:
            for piece in piece_list.copy():
                if piece.color not in color:
                    piece_list.remove(piece)
        if piece_type:
            for piece in piece_list.copy():
                if piece.type not in piece_type:
                    piece_list.remove(piece)
        return piece_list

    def get_alive_pieces(self):
        self.alive = self.get_pieces(
            piece_type=['pawn', 'rook', 'knight','bishop', 'queen', 'king']
        )

    def get_ib_moves(self):
        """Given each piece's position, get all moves for each piece that are
        within the boundaries of the board. Ignores castling."""
        for piece in self.alive:
            piece.ib_moves.reset()
            piece.get_ib_moves()

    def get_unobstructed_moves(self):
        """Given the board's pieces', each piece has its uo_moves attribute
        populated based on which moves have no pieces between it and dest.
        Knight/King/Pawn will always have the same ib_moves and uo_moves."""
        for piece in self.alive:
            if piece.type in ['knight', 'king']:
                for move, x, y in piece.ib_moves:
                    piece.uo_moves.add((move, x, y))
            else:
                for move, x, y in piece.ib_moves:
                    add = True
                    for btwn_pos in get_btwn(piece.pos, (x, y)):
                        if self[btwn_pos].occ:
                            add = False
                            break
                    if add: piece.uo_moves.add((move, x, y))

    def get_valid_pawn_moves(self, piece):
        """Get legal moves for pawns including en passant."""
        assert piece.type == 'pawn'
        for move, x, y in piece.uo_moves:
            # Advance Single Space
            if (move == 's_1' or move == 'n_1') and not self[x, y].occ:
                piece.v_moves.add((move, x, y))
            # Advance Two Spaces
            elif move.split('_')[-1] == '2' and piece.hist.len == 0:
                if not self[x, y].occ: piece.v_moves.add((move, x, y))
            elif len(move) == 4: # Only look at diagonal moves which have len 4
                occ = self[x, y].occ
                # Attacks
                if occ and occ.color != piece.color:
                    piece.v_moves.add((move, x, y))
                    piece.targets.add((occ.type, x, y))
                    occ.threats.add((piece.type, piece.x, piece.y))
                    continue
                elif occ and occ.color == piece.color:
                    occ.backups.add((piece.type, piece.x, piece.y))
                    piece.backing_up.add((occ.type, x, y))
                # En Passant
                elif not occ:
                    # Identify east/west neighbor in attack direction
                    neighbor = self[x, piece.y].occ
                    if (neighbor and neighbor.color != piece.color and
                        neighbor.type == 'pawn' and
                        neighbor.hist.len == 1 and
                        '2' in list(iter(neighbor.hist))[0][0]):
                        piece.v_moves.add((move, x, y))
                        piece.targets.add((neighbor.type, x, y))
                        neighbor.threats.add((piece.type, piece.x, piece.y))

    def get_valid_other_moves(self, piece):
        "Get legal moves for rooks excluding castles."""
        assert piece.type != 'pawn'
        for move, x, y in piece.uo_moves:
            occ = self[x, y].occ
            # If square is occupied by the enemy
            if occ and occ.color != piece.color:
                piece.v_moves.add((move, x, y))
                piece.targets.add((occ.type, x, y))
                occ.threats.add((piece.type, piece.x, piece.y))
            # If square is occupied by ally
            elif occ and occ.color == piece.color:
                occ.backups.add((piece.type, piece.x, piece.y))
                piece.backing_up.add((occ.type, x, y))
            # If square is empty
            elif not occ:
                piece.v_moves.add((move, x, y))

    def get_valid_moves(self):
        """Given the board's pieces', gets all legal moves for each piece.
        Does not consider pinned pieces, which are accounted for later."""
        move_dict = {
        'pawn':self.get_valid_pawn_moves,
        'rook':self.get_valid_other_moves,
        'knight':self.get_valid_other_moves,
        'bishop':self.get_valid_other_moves,
        'queen':self.get_valid_other_moves,
        'king':self.get_valid_other_moves
        }
        for piece in self.alive:
            move_dict[piece.type](piece)

    def are_squares_safe(self, square_list, color):
        """False if color has valid moves targeting any of squarelist."""
        pos_list = [square.pos for square in square_list]
        color_pieces = self.get_pieces(color=[color])
        for piece in color_pieces:
            for move, x, y in piece.v_moves:
                if (x, y) in pos_list:
                    return False # threatened
        return True

    def get_valid_castles(self):
        # Loop through what OUGHT to be the kings. Confirmed if hist.len==0.
        for k in [self[4,0].occ, self[4,7].occ]:
            if (not k or k.hist.len != 0):
                continue
            y = k.y
            color = list(set(['black','white']) - set([k.color]))[0]
            # Loop through what ought to be the rook's matching k's color
            rooks = [self[0,y].occ, self[7,y].occ]
            safe_sqs = [[2, 3, 4], [6, 5, 4]]
            emp_sqs = [(not self[1,y].occ and not self[2,y].occ
                       and not self[3,y].occ),
                       (not self[5,y].occ and not self[6,y].occ)]
            moves = ['c_q','c_k']
            # First element of each list has info for queenside castling
            for r, sqs, emp, move in zip(rooks, safe_sqs, emp_sqs, moves):
                if (not r or r.hist.len != 0):
                    continue
                if not emp:
                    continue
                square_list = [self[sq_x, y] for sq_x in sqs]
                if self.are_squares_safe(square_list, color):
                    k.v_moves.add((move, sqs[0], y))

    def reset_info(self):
        """Resets most information about the board's pieces."""
        for piece in self.alive:
            piece.uo_moves.reset()
            piece.v_moves.reset()
            piece.backups.reset()
            piece.backing_up.reset()
            piece.targets.reset()
            piece.threats.reset()

    def full_set_up(self, mode="standard"):
        """Set up board and generate all valid moves. Mode can be "random"."""
        if mode == "standard":
            self.set_up_board()
        elif mode == "random":
            self.set_up_board_randomly()
        self.get_alive_pieces()
        self.get_ib_moves()
        self.get_unobstructed_moves()
        self.get_valid_moves()
        self.get_valid_castles()

    def move_piece(self, piece, dest, validate=True, printer = False,
                   human=True):
        """Move piece, potentially capture, and update all values."""
        # Validate move
        if validate:
            assert piece
            assert dest in [(x, y) for move, x, y in piece.v_moves]
            assert piece.color == self.turn
        # Get move name
        move = piece.v_moves.filt([('x',dest[0]),('y',dest[1])])[0][0]
        # Format print statement
        origin_string = lookup_dict[piece.pos].replace('_',"").upper()
        dest_string = lookup_dict[dest].replace('_',"").upper()
        statement = "Moved " + piece.symbol + " from " + origin_string + \
                    " to " + dest_string + ". "
        dest_piece = self[dest].occ
        flavor = False
        if dest_piece: # Handle capture
            statement = statement + dest_piece.symbol + " has been captured!"
            self.alive.remove(dest_piece)
            self.move_history += [piece.symbol + ' ' + origin_string + ' > ' \
                                  + dest_string + ': ' + dest_piece.symbol \
                                  + " captured."]
            self.last_capture_turn = self.turn_num
            piece.kill_list += [dest_piece]
            if self.turn != self.player_color:
                flavor = True
        else:
            self.move_history += [piece.symbol + ' ' + origin_string + ' > ' + \
                                  dest_string + ': No capture.']
        # Update board information
        self[piece.pos].occ = None
        self[dest].occ = piece
        self.turn, self.nonturn = self.nonturn, self.turn
        self.turn_num += 1
        # Update piece information
        piece.x, piece.y = dest
        piece.pos = dest
        piece.hist.add((piece.v_moves.filt([('x',dest[0]),('y',dest[1])])))
        piece.get_ib_moves()
        # Handle castling
        if move == 'c_k' or move == 'c_q':
            if move == 'c_k':
                if printer: print("Kingside castle!")
                rook = self[7, piece.y].occ
                new_dest = (5, piece.y)
            elif move == 'c_q':
                if printer: print("Queenside castle!")
                rook = self[0, piece.y].occ
                new_dest = (3, piece.y)
            self.turn, self.nonturn = self.nonturn, self.turn
            self.turn_num -= 1
            self.move_piece(rook, new_dest, False, False)
            self.move_history = self.move_history[:-1]
        # Handle pawn promotion
        if piece.type == 'pawn' and dest[1] in [0, 7]:
            if human == False:
                promotion = 'queen'
                if printer: print(piece.symbol + " promoted to queen!")
            else:
                promotion = input("Pawn promotion! What piece would you like? "
                              "Enter the name of the piece \nyou want, such "
                              "as 'queen' or 'knight' without quotes: ")
            if promotion.lower() == 'quit':
                quit()
            elif promotion.lower() in ['queen', 'rook', 'knight', 'bishop']:
                invalid_type = False
            else:
                invalid_type = True
            while invalid_type:
                promotion = input("Try again. Name the type of piece you want "
                                  "your pawn to be promoted to.")
                if promotion.lower() == 'quit':
                    quit()
                elif promotion.lower() in ['queen', 'rook', 'knight', 'bishop']:
                    invalid_type = False
            new_queen = Piece(piece.color, promotion, piece.x, piece.y)
            self[piece.x, piece.y].occ = new_queen
            self.alive += [new_queen]
            new_queen.get_ib_moves()
            del piece
        # Update board
        self.reset_info()
        self.get_unobstructed_moves()
        self.get_valid_moves()
        self.get_valid_castles()
        # Check if in check for printing purposes
        check = False
        try:
            king = self.get_pieces(['king'],[self.turn])[0]
            if king.threats.len > 0:
                check = True
        except:
            pass
        # Display
        if printer:
            if check:
                statement = "Check! " + statement
            print(statement)
            if self.player_color == 'white':
                self.view(True)
            else:
                self.view(False)
            if flavor:
                flavor_spitter(dest_piece.type)
        return check

    def game_over_check(self):
        """The computer wins if the player loses all their pieces except the
        king, and the AI has a certain number of specific pieces. This is to
        avoid tedious endgame states (i.e. you can force a win with a rook
        and a king, but there is no need to go through the exercise.) Also
        ends the game if a certain number of turns have passed. Returns boolean
        for whether the game will end plus a reason."""
        # 50 Move Rule
        if self.turn_num - self.last_capture_turn >= 100:
            return True, "The game is a draw due to the 50-move rule."
        # AI has specific pieces and human has just a king
        reason = "You resign. Checkmate is trivial at this point."
        ai_pieces = []
        human_pieces = []
        for i in self.alive:
            if i.color != self.player_color:
                ai_pieces += [i.type]
            else:
                human_pieces += [i.type]
        if len(human_pieces) > 1:
            return False, ""
        else:
            if 'queen' in ai_pieces or 'rook' in ai_pieces:
                return True, reason
            elif ai_pieces.count('bishop') >= 2:
                return True, reason
            elif 'knight' in ai_pieces and 'bishop' in ai_pieces:
                # There are rare cases where this can't win, but I don't care.
                return True, reason
            else:
                return False, ""
