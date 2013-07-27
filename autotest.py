import sys
import ast
import _ast
import inspect

import restrict

##################
# Variable types #
##################

class Argument(object):

    def __init__(self, name):
        self.name = name

    def satisfy(self, restrictions):
        raise NotImplementedError("Must overwrite in child class")

    def __str__(self):
        return self.name

class Number(Argument):

    def satisfy(self, restrictions):
        final_r = restrict.Null(None)
        for r in restrictions:
            final_r = final_r.merge(r)
            if final_r is None:
                restriction_list = " and ".join((str(a) for a in restrictions))
                raise ValueError("Cannot satisfy restrictions:" + restriction_list)

        if isinstance(final_r, restrict.Null):
            return 0

        if isinstance(final_r, restrict.Equal):
            return final_r.value

        if isinstance(final_r, restrict.NotEqual):
            return final_r.value + 1

        if isinstance(final_r, restrict.NotIn):
            i = 1
            while i in final_r.value:
                i += 1
            return i

        raise NotImplementedError("Cannot satisfy restrictions: %s" % final_r)

    def __str__(self):
        return "Num(%s)" % super(Number, self).__str__()

class String(Argument):
    pass

################
# Restrictions #
################
class ArgumentRestrictions(object):

    def __init__(self, arg, restrictions):
        self.arg = arg
        self.restrictions = restrictions

    def satisfy(self):
        return self.arg, self.arg.satisfy(self.restrictions)

    def extend(self, restrictions):
        return ArgumentRestrictions(self.arg, self.restrictions + restrictions.restrictions)

    def __str__(self):
        return " and ".join((str(self.arg) + " " + str(r) for r in self.restrictions))

def get_arg_type(name):
    if name == "a":
        return Number

    if name == "b":
        return Number

class Stmt(object):

    @classmethod
    def split_equals(cls, left, right):
        if isinstance(left, _ast.Num) and isinstance(right, _ast.Name):
            swap = left
            left = right
            right = swap

        if isinstance(left, _ast.Name) and isinstance(right, _ast.Num):
            arg = Number(left.id)
            rest = restrict.Equal(right.n)
            return ArgumentRestrictions(arg, [rest]), ArgumentRestrictions(arg, [rest.inverse()])

        raise NotImplementedError("Can only compare name to number")

    @classmethod
    def split_lt(cls, left, right, and_eq):

        if isinstance(left, _ast.Name) and isinstance(right, _ast.Num):
            arg = Number(left.id)
            rest = restrict.LessThan(right.n, and_eq)

            return ArgumentRestrictions(arg, [rest]), ArgumentRestrictions(arg, [rest.inverse()])
        raise NotImplementedError("Can only compare name to number")

    @classmethod
    def split_compare(cls, compare):
        if len(compare.ops) > 1 or len(compare.comparators) > 1:
            raise NotImplementedError("Multiple operations in compare not supported")

        left = compare.left
        op = compare.ops[0]
        right = compare.comparators[0]

        if isinstance(op, _ast.Eq):
            return cls.split_equals(left, right) 

        if isinstance(op, _ast.Lt):
            return cls.split_lt(left, right, False)
        else:
            raise NotImplementedError("Operator not supported: %s" % op)

        raise NotImplementedError("Some unsupported operation occured!")

class Decision(object):
    
    def __init__(self, ast_if, body):
        self.ast_if = ast_if
        self.body = body
        self.children = None

        if ast_if is not None:
            test = ast_if.test
            if isinstance(test, _ast.Compare):
                r_t, r_f = Stmt.split_compare(test)

                self.r_t = r_t
                self.r_f = r_f
            else:
                raise NotImplementedError("Unknown _ast.If.test value: %s" % test)

    def load_children(self, parent_next=None):
        children = []
        for stmt in self.body:
            if isinstance(stmt, _ast.If):
                test = stmt.test
                body = stmt.body

                children.append(Decision(stmt, stmt.body))

            elif isinstance(stmt, _ast.Return):
                break
            elif isinstance(stmt, _ast.Raise):
                break

        for i in xrange(len(children)):
            my_next = parent_next
            if i != len(children) - 1:
                my_next = children[i + 1]

            child_count = children[i].load_children(my_next)
            if child_count != 0:
                children[i].set_true_next(children[i].children[0])
            else:
                children[i].set_true_next(my_next)

            children[i].set_false_next(my_next)

            #print children[i], "t_next =", children[i].n_t, "f_next =", children[i].n_t

        self.children = children
        return len(children)

    def set_true_next(self, n):
        self.n_t = n

    def set_false_next(self, n):
        self.n_f = n

    def gen_tests(self, restrictions, path=[]):
        #print "Visiting:", self, "via:", path

        r_t = restrictions.extend(self.r_t)
        r_f = restrictions.extend(self.r_f)

        path_t = path + [(self, True)]
        path_f = path + [(self, False)]

        # go into IF
        if self.n_t is not None:
            for test in self.n_t.gen_tests(r_t, path_t):
                yield test
        else: 
            yield r_t, path_t

        # dont go into IF
        if self.n_f is not None:
            for test in self.n_t.gen_tests(r_f, path_f):
                yield test
        else: 
            yield r_f, path_f

    def __str__(self):
        return "D%s" % self.ast_if.test.comparators[0].n
        #return "Decision %s@%x r_t=%s, r_f=%s" % (self.ast_if.test.comparators[0].n, id(self), self.r_t, self.r_f)

class AutoTest(object):

    @classmethod
    def load_f(cls, f):
        tree = ast.parse(inspect.getsource(f))

        f_tree = tree.body[0]
        assert isinstance(f_tree, _ast.FunctionDef)
        return f_tree

    @classmethod
    def load_args(cls, f_tree):
        args = []
        for arg in f_tree.args.args:
            args.append(get_arg_type(arg.id)(arg.id))
        return args

    @classmethod
    def gen_test_cases(cls, base):
        for r, path in base.gen_tests(ArgumentRestrictions(Number("a"), [])):
            try:
                arg, value = r.satisfy()
                yield arg, value
                print >> sys.stderr, arg.name, "==", value
            except ValueError as e:
                print >> sys.stderr,  e

    @classmethod
    def build(cls, f, module=None):
        if module is None and f.__module__ != "__main__":
            module = f.__module__

        if module is not None:
            name = module + "." + f.func_name

        tree = cls.load_f(f)
        #args = cls.load_args(tree)

        root_decision = Decision(None, tree.body)
        root_decision.load_children(None)

        success = ""
        errors = ""
        for arg, value in cls.gen_test_cases(root_decision.children[0]):
            try:
                result = f(value)
                success += "assert %s(%s) == %s\n" % (name, value, result)
            except Exception as e:
                e_name = str(e.__class__.__name__)
                errors += "try:\n"
                errors += "    %s(%s)\n" % (name, value)
                errors += "    assert False, 'Did not raise %s'\n" % e_name
                errors += "except %s:\n" % e_name
                errors += "     pass\n\n"

        if module is not None:
            print "import ", module
        print
        print success
        print errors

if __name__ == "__main__":
    import test_file

    f = AutoTest.build(test_file.lol)
